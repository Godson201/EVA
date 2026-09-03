"""Process liveness and dependency readiness endpoints."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.schemas.common import HealthResponse

router = APIRouter()


async def _run_check(check: Callable[[], Any]) -> bool:
    result = check()
    if inspect.isawaitable(result):
        result = await result
    return bool(result)


@router.get("/live", response_model=HealthResponse)
async def liveness(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
    )


@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def readiness(request: Request) -> HealthResponse | JSONResponse:
    settings = request.app.state.settings
    checks: dict[str, Callable[[], Any]] = request.app.state.readiness_checks
    results: dict[str, str] = {}

    for name, check in checks.items():
        try:
            results[name] = "ok" if await _run_check(check) else "unavailable"
        except Exception:
            results[name] = "error"

    is_ready = all(value == "ok" for value in results.values())
    payload = HealthResponse(
        status="ok" if is_ready else "unavailable",
        service=settings.app_name,
        version=settings.app_version,
        checks=results,
    )
    if is_ready:
        return payload
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=payload.model_dump())
