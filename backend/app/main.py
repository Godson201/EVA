"""Application factory for the modular EVA V2 API."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.v1.endpoints.translations import compatibility_router
from app.core.config import Settings, get_settings
from app.core.errors import install_exception_handlers
from app.core.lifecycle import lifespan
from app.core.logging import RequestContextMiddleware, configure_logging, get_logger

logger = get_logger(__name__)


def _load_legacy_app() -> FastAPI:
    """Load the original application only when compatibility mode is enabled.

    The import is deliberately deferred because the legacy module initializes
    Whisper and XTTS models at import time. Lightweight V2 commands and tests
    must never pay that startup cost.
    """

    backend_dir = str(Path(__file__).resolve().parents[1])
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    legacy_module = importlib.import_module("main")
    return legacy_module.app


def create_app(
    settings: Settings | None = None,
    *,
    include_legacy: bool | None = None,
    readiness_checks: dict[str, Callable[[], object]] | None = None,
) -> FastAPI:
    """Build an EVA application with explicitly supplied dependencies."""

    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    application = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        debug=resolved_settings.debug,
        docs_url="/docs" if resolved_settings.docs_enabled else None,
        redoc_url="/redoc" if resolved_settings.docs_enabled else None,
        openapi_url="/openapi.json" if resolved_settings.docs_enabled else None,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.readiness_checks = readiness_checks or {}

    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_exception_handlers(application)
    application.include_router(api_router, prefix=resolved_settings.api_v1_prefix)
    application.include_router(compatibility_router)

    legacy_enabled = resolved_settings.legacy_app_enabled if include_legacy is None else include_legacy
    if legacy_enabled:
        logger.warning("legacy_app_enabled", extra={"event_data": {"model_loading": True}})
        application.mount("/", _load_legacy_app(), name="legacy")

    return application


app = create_app()
