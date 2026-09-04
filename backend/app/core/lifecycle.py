"""Application startup and shutdown lifecycle."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = app.state.settings
    logger.info(
        "application_started",
        extra={
            "event_data": {
                "service": settings.app_name,
                "version": settings.app_version,
                "environment": settings.environment,
            }
        },
    )
    yield
    call_registry = getattr(app.state, "call_registry", None)
    if call_registry is not None:
        await call_registry.close_all()
    logger.info(
        "application_stopped",
        extra={"event_data": {"service": settings.app_name}},
    )
