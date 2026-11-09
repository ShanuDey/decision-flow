"""Liveness and readiness endpoints. HTTP only: no business logic here."""

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.settings import get_settings

router = APIRouter(tags=["ops"])

MLFLOW_TIMEOUT_SECONDS = 2.0

REQUIRED_CHECKS = ("postgres", "mlflow")


async def _check_postgres(session: AsyncSession) -> str:
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        return "unavailable"
    return "ok"


async def _check_mlflow() -> str:
    url = f"{get_settings().mlflow_tracking_uri.rstrip('/')}/health"
    try:
        async with httpx.AsyncClient(timeout=MLFLOW_TIMEOUT_SECONDS) as client:
            response = await client.get(url)
    except httpx.HTTPError:
        return "unavailable"
    return "ok" if response.status_code == 200 else "unavailable"


def _is_ready(checks: dict[str, str]) -> bool:
    return all(checks.get(name) == "ok" for name in REQUIRED_CHECKS)


@router.get("/health")
async def health() -> dict[str, str]:
    """Process is up. Does not check dependencies."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    response: Response, session: Annotated[AsyncSession, Depends(get_session)]
) -> dict[str, object]:
    """Dependencies reachable (Postgres, MLflow)."""
    checks = {
        "postgres": await _check_postgres(session),
        "mlflow": await _check_mlflow(),
    }
    ok = _is_ready(checks)
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if ok else "unavailable", "checks": checks}
