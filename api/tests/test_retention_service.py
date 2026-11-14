import logging

import pytest

from app.retention.service import run_cycle
from app.settings import Settings

pytestmark = pytest.mark.anyio


class FakeStore:
    def __init__(self, fail: str | None = None) -> None:
        self.calls: list[tuple[str, tuple]] = []
        self.fail = fail

    async def delete_runs_older_than(self, days: int, dry_run: bool = False) -> int:
        self.calls.append(("runs", (days, dry_run)))
        if self.fail == "runs":
            raise RuntimeError("secret@example.com")
        return 3

    async def delete_inactive_users(
        self, days: int, keep_emails: list[str], dry_run: bool = False
    ) -> int:
        self.calls.append(("users", (days, tuple(keep_emails), dry_run)))
        return 2

    async def delete_expired_auth_sessions(self, dry_run: bool = False) -> int:
        self.calls.append(("sessions", (dry_run,)))
        return 5

    async def auth_schema_exists(self) -> bool:
        return True


class Traces:
    def __init__(self) -> None:
        self.calls: list[int] = []

    async def __call__(self, days: int) -> int | None:
        self.calls.append(days)
        return 7


def settings(**fields: object) -> Settings:
    return Settings(_env_file=None, **fields)


async def test_nothing_runs_when_every_value_is_zero() -> None:
    store = FakeStore()
    report = await run_cycle(store, settings(), Traces())
    assert store.calls == []
    assert report.model_dump() == {
        "dry_run": False,
        "runs": 0,
        "traces": None,
        "users": 0,
        "sessions": 0,
    }


async def test_runs_and_traces_follow_the_run_setting_and_users_the_user_setting() -> None:
    store, traces = FakeStore(), Traces()
    report = await run_cycle(
        store,
        settings(run_retention_days=7, user_retention_days=14, retention_keep_emails=" Me@X.com "),
        traces,
    )
    assert store.calls == [
        ("runs", (7, False)),
        ("users", (14, ("me@x.com",), False)),
        ("sessions", (False,)),
    ]
    assert traces.calls == [7]
    assert (report.runs, report.traces, report.users, report.sessions) == (3, 7, 2, 5)


async def test_with_only_user_retention_runs_stay_but_traces_follow_the_user_period() -> None:
    store, traces = FakeStore(), Traces()
    await run_cycle(store, settings(user_retention_days=3), traces)
    assert [name for name, _ in store.calls] == ["users", "sessions"]
    assert traces.calls == [3]


async def test_traces_use_the_shorter_of_the_two_periods() -> None:
    traces = Traces()
    await run_cycle(FakeStore(), settings(run_retention_days=30, user_retention_days=7), traces)
    assert traces.calls == [7]


async def test_a_missing_auth_schema_is_warned_about(caplog: pytest.LogCaptureFixture) -> None:
    class NoAuth(FakeStore):
        async def auth_schema_exists(self) -> bool:
            return False

    with caplog.at_level(logging.WARNING):
        await run_cycle(NoAuth(), settings(user_retention_days=3), Traces())
    assert "no auth schema" in caplog.text


async def test_a_dry_run_deletes_no_traces_and_tells_the_store() -> None:
    store, traces = FakeStore(), Traces()
    report = await run_cycle(store, settings(run_retention_days=7, retention_dry_run=True), traces)
    assert store.calls[0] == ("runs", (7, True))
    assert traces.calls == []
    assert report.dry_run is True and report.traces is None


async def test_a_failing_step_does_not_stop_the_rest_or_leak_its_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = FakeStore(fail="runs")
    with caplog.at_level(logging.INFO):
        report = await run_cycle(
            store, settings(run_retention_days=7, user_retention_days=7), Traces()
        )
    assert (report.runs, report.users, report.sessions) == (0, 2, 5)
    assert "secret@example.com" not in caplog.text
    assert "RuntimeError" in caplog.text
