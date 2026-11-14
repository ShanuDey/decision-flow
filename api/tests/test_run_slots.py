import uuid

import pytest

from app.errors import ApiError
from app.limits import Limits
from app.runs.slots import RunSlots

pytestmark = pytest.mark.anyio

A, B = uuid.uuid4(), uuid.uuid4()


def slots(**limits: int) -> RunSlots:
    return RunSlots(Limits(_env_file=None, **limits))


async def test_the_app_wide_cap_refuses_the_next_run() -> None:
    s = slots(max_concurrent_runs=1)
    async with s.hold(A):
        with pytest.raises(ApiError) as refused:
            async with s.hold(B):
                pass
    assert refused.value.status == 429
    assert refused.value.body.code == "run_limit"
    assert refused.value.body.details["scope"] == "app"
    assert refused.value.headers == {"Retry-After": "5"}


@pytest.mark.parametrize(("timeout", "expected"), [(0, "5"), (2, "2"), (30, "5"), (300, "5")])
def test_retry_after_never_exceeds_the_run_timeout_or_five_seconds(
    timeout: int, expected: str
) -> None:
    assert slots(run_timeout_seconds=timeout).retry_after == expected


async def test_the_refusal_carries_the_notice_only_when_one_is_set() -> None:
    plain = slots(max_concurrent_runs=1)
    noted = slots(
        max_concurrent_runs=1, limit_notice="Free demo.", limit_notice_url="https://x.test"
    )
    for s, expected in (
        (plain, {}),
        (noted, {"notice": "Free demo.", "notice_url": "https://x.test"}),
    ):
        async with s.hold(A):
            with pytest.raises(ApiError) as refused:
                async with s.hold(B):
                    pass
        details = refused.value.body.details
        assert {k: v for k, v in details.items() if k.startswith("notice")} == expected
        assert refused.value.body.message.startswith("Too many runs")


async def test_a_workspace_cap_does_not_block_other_workspaces() -> None:
    s = slots(max_concurrent_runs=0, max_concurrent_runs_per_workspace=1)
    async with s.hold(A):
        with pytest.raises(ApiError) as refused:
            async with s.hold(A):
                pass
        assert refused.value.body.details["scope"] == "workspace"
        async with s.hold(B):
            pass


async def test_the_slot_is_freed_after_the_run_and_after_an_error() -> None:
    s = slots(max_concurrent_runs=1)
    async with s.hold(A):
        pass
    with pytest.raises(RuntimeError):
        async with s.hold(A):
            raise RuntimeError("boom")
    async with s.hold(A):
        assert s.running == 1
    assert s.running == 0 and not s.by_workspace


async def test_zero_means_no_cap() -> None:
    s = slots(max_concurrent_runs=0, max_concurrent_runs_per_workspace=0)
    async with s.hold(A), s.hold(A), s.hold(A):
        assert s.running == 3


async def test_a_refused_run_takes_no_slot() -> None:
    s = slots(max_concurrent_runs=1)
    async with s.hold(A):
        with pytest.raises(ApiError):
            async with s.hold(B):
                pass
        assert s.running == 1 and B not in s.by_workspace
