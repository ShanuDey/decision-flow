import uuid
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Request

from app.errors import ApiError
from app.limits import Limits

MAX_RETRY_AFTER_SECONDS = 5


class RunSlots:
    """Counts runs in flight; in memory, so per process."""

    def __init__(self, limits: Limits) -> None:
        self.app_cap = limits.max_concurrent_runs
        self.workspace_cap = limits.max_concurrent_runs_per_workspace
        self.notice = limits.notice_details()
        # A slot frees when a run ends, so waiting longer than the run timeout never helps.
        self.retry_after = str(
            min(limits.run_timeout_seconds or MAX_RETRY_AFTER_SECONDS, MAX_RETRY_AFTER_SECONDS)
        )
        self.running = 0
        self.by_workspace: Counter[uuid.UUID] = Counter()

    def _busy(self, scope: str, cap: int) -> ApiError:
        return ApiError(
            429,
            "run_limit",
            f"Too many runs are in progress ({cap} at once); try again shortly",
            {"scope": scope, "limit": cap, **self.notice},
            {"Retry-After": self.retry_after},
        )

    @asynccontextmanager
    async def hold(self, workspace_id: uuid.UUID) -> AsyncIterator[None]:
        # No await between the check and the increment, so one event loop needs no lock.
        if self.app_cap and self.running >= self.app_cap:
            raise self._busy("app", self.app_cap)
        if self.workspace_cap and self.by_workspace[workspace_id] >= self.workspace_cap:
            raise self._busy("workspace", self.workspace_cap)
        self.running += 1
        self.by_workspace[workspace_id] += 1
        try:
            yield
        finally:
            self.running -= 1
            self.by_workspace[workspace_id] -= 1
            if not self.by_workspace[workspace_id]:
                del self.by_workspace[workspace_id]


def get_run_slots(request: Request) -> RunSlots:
    return request.app.state.run_slots
