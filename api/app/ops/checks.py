import asyncio
import time

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import tracing
from app.ops.schemas import CheckStatus
from app.settings import get_settings

CHECK_TIMEOUT_SECONDS = 2.0
DATABASE_PROBE_TTL_SECONDS = 5.0

# MLflow is the audit store: a decision without a trace is a failure.
REQUIRED_CHECKS = ("postgres", "mlflow")

_probe_cache: dict[str, tuple[float, bool]] = {}


async def check_postgres(session: AsyncSession) -> CheckStatus:
    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SECONDS):
            await session.execute(text("SELECT 1"))
    except Exception:
        return "unavailable"
    return "ok"


async def _database_reachable(uri: str) -> bool:
    cached = _probe_cache.get(uri)
    if cached is not None and time.monotonic() - cached[0] < DATABASE_PROBE_TTL_SECONDS:
        return cached[1]
    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SECONDS):
            reachable = await asyncio.to_thread(
                tracing.database_reachable, uri, CHECK_TIMEOUT_SECONDS
            )
    except TimeoutError:
        reachable = False
    _probe_cache[uri] = (time.monotonic(), reachable)
    return reachable


async def check_mlflow() -> CheckStatus:
    settings = get_settings()
    if not tracing.is_configured():
        tracing.warm_up(settings)  # retries after a failed start, so /ready recovers by itself
        return "unavailable"
    uri = settings.mlflow_tracking_uri
    if not uri.startswith(("http://", "https://")):
        return "ok" if await _database_reachable(uri) else "unavailable"
    url = f"{uri.rstrip('/')}/health"
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
