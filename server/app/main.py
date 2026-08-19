"""FastAPI application factory."""

from __future__ import annotations

import logging
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine

from . import __version__
from .config import Settings, get_settings
from .db import build_engine, build_session_factory
from .edge_monitor import check_and_record
from .dashboard_auth import read_session_token
from .routes import auth, catalog, edge, health, ingest, telemetry


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    database_engine = engine or build_engine(settings.database_url)

    session_factory = build_session_factory(database_engine)

    async def monitor_edge() -> None:
        while True:
            await asyncio.sleep(settings.pi_status_interval_seconds)
            try:
                await asyncio.to_thread(check_and_record, settings, session_factory)
            except Exception:
                logging.getLogger(__name__).exception("Scheduled Pi status check failed")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        monitor_task = None
        if settings.pi_api_url:
            monitor_task = asyncio.create_task(monitor_edge())
        try:
            yield
        finally:
            if monitor_task:
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass
            database_engine.dispose()

    app = FastAPI(
        title="AC Metrics",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = database_engine
    app.state.session_factory = session_factory

    @app.middleware("http")
    async def require_dashboard_session(request: Request, call_next):
        path = request.url.path
        public_api = (
            path in {"/health", "/ready", "/v1/telemetry/batches"}
            or path.startswith("/api/v1/auth/")
        )
        if path.startswith("/api") and not public_api:
            session = read_session_token(
                request.cookies.get(settings.dashboard_cookie_name),
                settings.dashboard_session_secret.get_secret_value(),
                settings.dashboard_username,
            )
            if session is None:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "dashboard authentication required"},
                    headers={"Cache-Control": "no-store"},
                )
            request.state.dashboard_username = session.username
        response = await call_next(request)
        if path.startswith("/api/v1/auth/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(health.router)
    app.include_router(ingest.router)
    app.include_router(auth.router)
    app.include_router(catalog.router)
    app.include_router(telemetry.router)
    app.include_router(edge.router)
    dashboard = Path(__file__).with_name("static")
    if dashboard.is_dir():
        app.mount("/", StaticFiles(directory=dashboard, html=True), name="dashboard")
    return app


app = create_app()
