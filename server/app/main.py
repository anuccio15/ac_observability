"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import Engine

from . import __version__
from .config import Settings, get_settings
from .db import build_engine, build_session_factory
from .routes import catalog, health, ingest


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
    return app


app = create_app()
