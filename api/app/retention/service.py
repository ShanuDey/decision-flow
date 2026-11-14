"""Retention policy: what is old enough to delete. Counts only are logged, never data."""

import logging
from collections.abc import Awaitable, Callable
from typing import Protocol

from app.engine.base import FrozenBaseModel
from app.settings import Settings

log = logging.getLogger(__name__)

DeleteTraces = Callable[[int], Awaitable[int | None]]


class RetentionStoreLike(Protocol):
    async def delete_runs_older_than(self, days: int, dry_run: bool = False) -> int: ...

    async def delete_inactive_users(
        self, days: int, keep_emails: list[str], dry_run: bool = False
    ) -> int: ...

    async def delete_expired_auth_sessions(self, dry_run: bool = False) -> int: ...

    async def auth_schema_exists(self) -> bool: ...


class RetentionReport(FrozenBaseModel):
    dry_run: bool
    runs: int = 0
    traces: int | None = None
    users: int = 0
    sessions: int = 0


async def run_cycle(
    store: RetentionStoreLike, settings: Settings, delete_traces: DeleteTraces
) -> RetentionReport:
    """One pass. A failing step is logged and skipped so it cannot block the others."""
    dry = settings.retention_dry_run
    counts: dict[str, int | None] = {}

    async def step(name: str, action: Callable[[], Awaitable[int | None]]) -> None:
        try:
            counts[name] = await action()
        except Exception as exc:  # the message can echo SQL parameters, so log the type only
            log.warning("retention step %r failed: %s", name, type(exc).__name__)

    if days := settings.run_retention_days:
        await step("runs", lambda: store.delete_runs_older_than(days, dry))
    # A deleted account's traces still hold its run data, so the shorter period governs them.
    periods = [d for d in (settings.run_retention_days, settings.user_retention_days) if d]
    if periods and not dry:
        trace_days = min(periods)
        await step("traces", lambda: delete_traces(trace_days))
    if days := settings.user_retention_days:
        keep = settings.retention_keep_emails
        await step("users", lambda: store.delete_inactive_users(days, keep, dry))
        if not await store.auth_schema_exists():
            log.warning("retention: no auth schema here; sign-in records are not deleted")
    if settings.retention_enabled:
        await step("sessions", lambda: store.delete_expired_auth_sessions(dry))

    report = RetentionReport(dry_run=dry, **counts)
    log.info("retention cycle: %s", report.model_dump())
    return report
