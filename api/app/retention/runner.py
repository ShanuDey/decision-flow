"""The in-process timer. Stateless: a restart just runs the next cycle."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app import tracing
from app.retention.service import RetentionReport, run_cycle
from app.retention.store import RetentionStore
from app.settings import Settings

log = logging.getLogger(__name__)

INITIAL_DELAY_SECONDS = 30
LOCK_KEY = 0x646563666C6F77  # one cycle at a time across instances


async def run_forever(
    cycle: Callable[[], Awaitable[object]],
    interval_seconds: float,
    initial_delay_seconds: float = INITIAL_DELAY_SECONDS,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    await sleep(initial_delay_seconds)
    while True:
        try:
            await cycle()
        except Exception as exc:
            log.warning("retention cycle failed: %s", type(exc).__name__)
        await sleep(interval_seconds)


async def locked_cycle(engine: AsyncEngine, settings: Settings) -> RetentionReport | None:
    """None when another instance holds the lock."""
    async with engine.connect() as lock:
        got = await lock.scalar(select(func.pg_try_advisory_lock(LOCK_KEY)))
        await lock.commit()  # the lock belongs to the connection, so no transaction stays open
        if not got:
            return None
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                return await run_cycle(
                    RetentionStore(session),
                    settings,
                    lambda days: tracing.delete_traces_older_than(settings, days),
                )
        finally:
            try:
                await lock.scalar(select(func.pg_advisory_unlock(LOCK_KEY)))
            except Exception as exc:  # a dropped connection releases the lock by itself
                log.warning("retention lock release failed: %s", type(exc).__name__)


def start(engine: AsyncEngine, settings: Settings) -> "asyncio.Task[None] | None":
    if not settings.retention_enabled:
        return None
    return asyncio.create_task(
        run_forever(
            lambda: locked_cycle(engine, settings), settings.retention_interval_minutes * 60
        )
    )
