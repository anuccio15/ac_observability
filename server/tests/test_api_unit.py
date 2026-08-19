from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.edge_monitor import probe_pi
from .helpers import (
    DASHBOARD_PASSWORD,
    DASHBOARD_PASSWORD_HASH,
    DASHBOARD_SESSION_SECRET,
    EDGE_TOKEN,
    edge_headers,
    gzip_json,
    login_dashboard,
    make_batch,
)


def build_client(**overrides) -> TestClient:
    overrides.setdefault("dashboard_password_hash", DASHBOARD_PASSWORD_HASH)
    overrides.setdefault("dashboard_session_secret", DASHBOARD_SESSION_SECRET)
    settings = Settings(
        database_url="postgresql+psycopg://unused:unused@127.0.0.1:1/unused",
        edge_api_token=EDGE_TOKEN,
        **overrides,
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


def test_dashboard_api_requires_login() -> None:
    with build_client() as client:
        response = client.get("/api/v1/devices")
    assert response.status_code == 401
    assert response.json()["detail"] == "dashboard authentication required"


def test_dashboard_login_and_logout() -> None:
    with build_client() as client:
        rejected = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "incorrect"},
        )
        assert rejected.status_code == 401

        accepted = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": DASHBOARD_PASSWORD},
        )
        assert accepted.status_code == 200
        assert accepted.json() == {"authenticated": True, "username": "admin"}
        assert client.get("/api/v1/auth/session").json()["authenticated"] is True

        logged_out = client.post("/api/v1/auth/logout")
        assert logged_out.status_code == 200
        assert client.get("/api/v1/auth/session").json()["authenticated"] is False


def test_manual_sync_requires_pi_configuration() -> None:
    with build_client() as client:
        login_dashboard(client)
        response = client.post("/api/v1/edge/sync")
    assert response.status_code == 503


def test_manual_sync_proxies_the_acknowledged_pi_result(monkeypatch) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"accepted":true,"queued_samples":14,"delivered_samples":14,"pending_samples":0,"completed_at":"2026-08-15T00:00:00Z"}'

    def fake_urlopen(request, timeout):
        assert request.full_url == "http://pi:8787/api/v1/flush"
        assert request.headers["Authorization"] == "Bearer pi-secret"
        assert timeout == 5
        return Response()

    monkeypatch.setattr("app.routes.edge.urllib.request.urlopen", fake_urlopen)
    with build_client(
        pi_api_url="http://pi:8787",
        pi_api_token="pi-secret",
        pi_sync_timeout_seconds=5,
    ) as client:
        login_dashboard(client)
        response = client.post("/api/v1/edge/sync")
    assert response.status_code == 200
    assert response.json()["edge"]["delivered_samples"] == 14
    assert response.json()["edge"]["pending_samples"] == 0


def test_pi_probe_classifies_bluetooth_disconnect(monkeypatch) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"bluetooth_connected":false,"collector":{"last_frame_at":"2026-08-17T20:00:00Z","last_error":"not found"}}'

    monkeypatch.setattr("app.edge_monitor.urllib.request.urlopen", lambda *_args, **_kwargs: Response())
    settings = Settings(
        database_url="postgresql+psycopg://unused:unused@127.0.0.1:1/unused",
        edge_api_token=EDGE_TOKEN,
        pi_api_url="http://pi:8787",
    )
    result = probe_pi(settings)
    assert result["state"] == "bosch_disconnected"
    assert result["pi_reachable"] is True
