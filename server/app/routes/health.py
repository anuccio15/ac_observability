"""Liveness and database readiness endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import text

from app import __version__


router = APIRouter(tags=["operations"])


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "timestamp": datetime.now(timezone.utc),
    }


@router.get("/ready")
def ready(request: Request, response: Response) -> dict:
    try:
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            migration = connection.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            ).scalar_one()
    except Exception as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not-ready", "database": "unavailable", "detail": type(exc).__name__}
    return {"status": "ready", "database": "ok", "migration": migration}
