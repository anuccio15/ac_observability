from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.main import create_app
from app.models import BatchEvent, Device, IngestBatch, MetricCatalogEntry, TelemetryEvent
from .helpers import EDGE_TOKEN, edge_headers, gzip_json, make_batch, make_sample


TEST_DATABASE_URL = os.getenv("AC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="AC_TEST_DATABASE_URL is required for PostgreSQL integration tests",
)


@pytest.fixture()
def database_engine():
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM batch_events"))
        connection.execute(text("DELETE FROM decoded_projections"))
        connection.execute(text("DELETE FROM telemetry_events"))
        connection.execute(text("DELETE FROM ingest_batches"))
        connection.execute(text("DELETE FROM devices"))
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def client(database_engine):
    settings = Settings(database_url=TEST_DATABASE_URL, edge_api_token=EDGE_TOKEN)
    with TestClient(create_app(settings=settings, engine=database_engine)) as test_client:
        yield test_client


def test_ingests_and_idempotently_acknowledges_batch(client, database_engine) -> None:
    payload = make_batch()
    first = client.post(
        "/v1/telemetry/batches",
        content=gzip_json(payload),
        headers=edge_headers(),
    )
    assert first.status_code == 200, first.text
    assert first.json() == {
        "batch_id": payload["batch_id"],
        "accepted": True,
        "accepted_samples": 1,
        "duplicate": False,
    }

    duplicate = client.post(
        "/v1/telemetry/batches",
        content=gzip_json(payload),
        headers=edge_headers(),
    )
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["duplicate"] is True

    with Session(database_engine) as session:
        assert session.scalar(select(func.count()).select_from(Device)) == 1
        assert session.scalar(select(func.count()).select_from(IngestBatch)) == 1
        assert session.scalar(select(func.count()).select_from(TelemetryEvent)) == 1
        assert session.scalar(select(func.count()).select_from(BatchEvent)) == 1
        event = session.scalar(select(TelemetryEvent))
        assert len(event.raw_frame) == 167
        assert event.decoder_version == 1


def test_rejects_conflicting_batch_content(client) -> None:
    payload = make_batch()
    accepted = client.post(
        "/v1/telemetry/batches",
        content=gzip_json(payload),
        headers=edge_headers(),
    )
    assert accepted.status_code == 200
    payload["samples"][0]["metrics"]["compressor_set_hz"] = 99
    conflict = client.post(
        "/v1/telemetry/batches",
        content=gzip_json(payload),
        headers=edge_headers(),
    )
    assert conflict.status_code == 409


def test_overlapping_batches_reuse_identical_events(client, database_engine) -> None:
    first_sample = make_sample()
    first_batch = make_batch([first_sample])
    assert client.post(
        "/v1/telemetry/batches",
        content=gzip_json(first_batch),
        headers=edge_headers(),
    ).status_code == 200

    second_sample = make_sample("2026-08-13T21:08:51+00:00", compressor_hz=23)
    second_batch = make_batch([first_sample, second_sample])
    response = client.post(
        "/v1/telemetry/batches",
        content=gzip_json(second_batch),
        headers=edge_headers(),
    )
    assert response.status_code == 200, response.text
    with Session(database_engine) as session:
        assert session.scalar(select(func.count()).select_from(IngestBatch)) == 2
        assert session.scalar(select(func.count()).select_from(TelemetryEvent)) == 2
        assert session.scalar(select(func.count()).select_from(BatchEvent)) == 3


def test_metric_catalog_is_seeded(client, database_engine) -> None:
    response = client.get("/api/v1/metrics/catalog")
    assert response.status_code == 200
    keys = {metric["key"] for metric in response.json()["metrics"]}
    assert "compressor_set_hz" in keys
    assert "candidate_ac_input_voltage_v" in keys
    with Session(database_engine) as session:
        assert session.scalar(select(func.count()).select_from(MetricCatalogEntry)) >= 20


def test_dashboard_query_endpoints(client) -> None:
    samples = [
        make_sample("2026-08-13T21:08:46+00:00", compressor_hz=20),
        make_sample("2026-08-13T21:08:51+00:00", compressor_hz=30),
        make_sample("2026-08-13T21:08:56+00:00", compressor_hz=40),
    ]
    samples[-1]["urgent"] = True
    samples[-1]["urgent_reason"] = "test fault"
    response = client.post(
        "/v1/telemetry/batches",
        content=gzip_json(make_batch(samples)),
        headers=edge_headers(),
    )
    assert response.status_code == 200, response.text

    devices = client.get("/api/v1/devices")
    assert devices.status_code == 200
    assert devices.json()["devices"][0]["event_count"] == 3
    assert devices.json()["devices"][0]["urgent_count"] == 1

    latest = client.get("/api/v1/telemetry/latest")
    assert latest.status_code == 200
    assert latest.json()["sample"]["metrics"]["compressor_set_hz"] == 40

    series = client.get(
        "/api/v1/telemetry/series",
        params={
            "metrics": "compressor_set_hz,outdoor_ambient_t4_f",
            "start": "2026-08-13T21:00:00Z",
            "end": "2026-08-13T22:00:00Z",
            "max_points": 500,
        },
    )
    assert series.status_code == 200, series.text
    assert series.json()["series"]["compressor_set_hz"]["points"]

    summary = client.get("/api/v1/summary", params={"hours": 24 * 31})
    assert summary.status_code == 200
    assert summary.json()["latest"]["metrics"]["compressor_set_hz"] == 40

    cycles = client.get(
        "/api/v1/cycles",
        params={
            "start": "2026-08-13T21:00:00Z",
            "end": "2026-08-13T22:00:00Z",
        },
    )
    assert cycles.status_code == 200, cycles.text
    assert cycles.json()["cycles"][0]["mode"] == "cooling"
    assert cycles.json()["cycles"][0]["sample_count"] == 3

    faults = client.get("/api/v1/faults")
    assert faults.status_code == 200
    assert faults.json()["faults"][0]["urgent_reason"] == "test fault"


def test_series_rejects_unknown_or_text_metrics(client) -> None:
    payload = make_batch()
    assert client.post(
        "/v1/telemetry/batches",
        content=gzip_json(payload),
        headers=edge_headers(),
    ).status_code == 200
    response = client.get(
        "/api/v1/telemetry/series",
        params={
            "metrics": "mode,not_a_metric",
            "start": "2026-08-13T21:00:00Z",
            "end": "2026-08-13T22:00:00Z",
        },
    )
    assert response.status_code == 422
