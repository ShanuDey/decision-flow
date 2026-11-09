import asyncio

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ops.schemas import CheckStatus
from app.settings import get_settings

CHECK_TIMEOUT_SECONDS = 2.0

# MLflow is the audit store: a decision without a trace is a failure.
REQUIRED_CHECKS = ("postgres", "mlflow")


async def check_postgres(session: AsyncSession) -> CheckStatus:
    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SECONDS):
            await session.execute(text("SELECT 1"))
    except Exception:
        return "unavailable"
    return "ok"


async def check_mlflow() -> CheckStatus:
    url = f"{get_settings().mlflow_tracking_uri.rstrip('/')}/health"
    try:
        async with httpx.AsyncClient(timeout=CHECK_TIMEOUT_SECONDS) as client:
            response = await client.get(url)
    except httpx.HTTPError:
        return "unavailable"
    return "ok" if response.status_code == 200 else "unavailable"


async def run_checks(session: AsyncSession) -> dict[str, CheckStatus]:
    return {
        "postgres": await check_postgres(session),
        "mlflow": await check_mlflow(),
    }


def is_ready(results: dict[str, CheckStatus]) -> bool:
    return all(results.get(name) == "ok" for name in REQUIRED_CHECKS)
