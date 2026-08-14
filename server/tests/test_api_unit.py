from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from .helpers import EDGE_TOKEN, edge_headers, gzip_json, make_batch


def build_client() -> TestClient:
    settings = Settings(
        database_url="postgresql+psycopg://unused:unused@127.0.0.1:1/unused",
        edge_api_token=EDGE_TOKEN,
    )
    return TestClient(create_app(settings=settings))


def test_health_does_not_depend_on_database() -> None:
    with build_client() as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_fails_when_database_is_unavailable() -> None:
    with build_client() as client:
        response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not-ready"


def test_ingestion_requires_edge_token_before_reading_body() -> None:
    with build_client() as client:
        response = client.post(
            "/v1/telemetry/batches",
            content=gzip_json(make_batch()),
            headers=edge_headers("wrong-token"),
        )
    assert response.status_code == 401


def test_ingestion_requires_gzip() -> None:
    headers = edge_headers()
    headers.pop("Content-Encoding")
    with build_client() as client:
        response = client.post(
            "/v1/telemetry/batches",
            content=b"{}",
            headers=headers,
        )
    assert response.status_code == 415
