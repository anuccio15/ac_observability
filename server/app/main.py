"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine

from . import __version__
from .config import Settings, get_settings
from .db import build_engine, build_session_factory
from .routes import catalog, health, ingest, telemetry


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    database_engine = engine or build_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
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
    app.state.session_factory = build_session_factory(database_engine)
    app.include_router(health.router)
    app.include_router(ingest.router)
    app.include_router(catalog.router)
    app.include_router(telemetry.router)
    dashboard = Path(__file__).with_name("static")
    if dashboard.is_dir():
        app.mount("/", StaticFiles(directory=dashboard, html=True), name="dashboard")
    return app


app = create_app()
