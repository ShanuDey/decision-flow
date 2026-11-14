"""Liveness and readiness endpoints. HTTP only: no business logic here."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import ErrorResponse
from app.ops import checks
from app.ops.schemas import HealthResponse, ReadyResponse

router = APIRouter(tags=["ops"])


@router.get("/health")
async def health() -> HealthResponse:
    """Process is up. Does not check dependencies."""
    return HealthResponse(status="ok")


@router.get("/ready", responses={503: {"model": ReadyResponse}, 429: {"model": ErrorResponse}})
async def ready(
    response: Response, session: Annotated[AsyncSession, Depends(get_session)]
) -> ReadyResponse:
    """Dependencies reachable (Postgres, MLflow)."""
    results = await checks.run_checks(session)
    ok = checks.is_ready(results)
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyResponse(status="ok" if ok else "unavailable", checks=results)
