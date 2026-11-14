import asyncio
import uuid
from collections.abc import Awaitable, Callable

import pytest

from app.retention.runner import run_forever
from app.workspaces.activity import TOUCH_INTERVAL_SECONDS, ActivityThrottle

pytestmark = pytest.mark.anyio


class Stop(Exception):
    pass


def sleeper(limit: int) -> tuple[list[float], Callable[[float], Awaitable[None]]]:
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)
        if len(slept) > limit:
            raise Stop

    return slept, sleep


async def test_waits_first_then_runs_a_cycle_every_interval() -> None:
    slept, sleep = sleeper(3)
    runs: list[int] = []

    async def cycle() -> None:
        runs.append(1)

    with pytest.raises(Stop):
        await run_forever(cycle, 600, initial_delay_seconds=30, sleep=sleep)
    assert slept == [30, 600, 600, 600]
    assert len(runs) == 3


async def test_a_failing_cycle_does_not_stop_the_timer() -> None:
    slept, sleep = sleeper(2)
    calls: list[int] = []

    async def cycle() -> None:
        calls.append(1)
        raise RuntimeError("boom")

    with pytest.raises(Stop):
        await run_forever(cycle, 60, initial_delay_seconds=0, sleep=sleep)
    assert len(calls) == 2


async def test_cancelling_the_task_stops_it_cleanly() -> None:
    async def cycle() -> None: ...

    task = asyncio.create_task(run_forever(cycle, 3600, initial_delay_seconds=3600))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def test_last_seen_is_written_at_most_once_an_hour_per_user() -> None:
    now = [0.0]
    throttle = ActivityThrottle(clock=lambda: now[0])
    user, other = uuid.uuid4(), uuid.uuid4()
    assert throttle.due(user) and throttle.due(other)
    assert not throttle.due(user)
    now[0] = TOUCH_INTERVAL_SECONDS - 1
    assert not throttle.due(user)
    now[0] = TOUCH_INTERVAL_SECONDS
    assert throttle.due(user)


async def test_a_signed_in_request_records_activity_once(client, workspace_store) -> None:  # noqa: ANN001
    for _ in range(3):
        assert (await client.get("/flows")).status_code == 200
    assert len(workspace_store.touched) == 1
