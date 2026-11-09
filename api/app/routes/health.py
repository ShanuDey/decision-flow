"""Liveness and readiness endpoints. HTTP only: no business logic here."""

from fastapi import APIRouter

router = APIRouter(tags=["ops"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Process is up. Does not check dependencies."""
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> dict[str, object]:
    """Dependencies reachable. Postgres and MLflow checks are added in later steps."""
    checks: dict[str, str] = {}
    return {"status": "ok", "checks": checks}
