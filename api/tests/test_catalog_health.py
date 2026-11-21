import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.catalog.health import (
    BROKEN_AFTER,
    MAX_AGE,
    MIN_REFRESH_SECONDS,
    TTL_SECONDS,
    EntryHealth,
    HealthSource,
    next_health,
    parse_report,
)

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 11, 21, 3, 0, tzinfo=UTC)
BASE = "https://health.test/branch"
BROKEN_GITHUB = {
    "connection-type/github": {
        "status": "broken",
        "failures": 2,
        "checked_at": NOW.isoformat(),
        "reason": "x",
    }
}


def report(entries: dict[str, Any] | None = None, **top: Any) -> bytes:
    body = {
        "schema_version": 1,
        "generated_at": NOW.isoformat(),
        "entries": BROKEN_GITHUB if entries is None else entries,
    }
    return json.dumps({**body, **top}).encode()


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class Host:
    def __init__(self, body: bytes | None) -> None:
        self.body = body
        self.requests: list[str] = []
        self.down = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request.url.path)
        if self.down:
            raise httpx.ConnectError("down")
        if self.body is None:
            return httpx.Response(404)
        return httpx.Response(200, content=self.body)

    def source(self, clock: Callable[[], float], now: datetime = NOW) -> HealthSource:
        return HealthSource(
            BASE, transport=httpx.MockTransport(self.handler), clock=clock, now=lambda: now
        )


class TestNextHealth:
    def test_a_pass_is_ok_with_no_failures(self) -> None:
        result = next_health(None, None, NOW)
        assert (result.status, result.failures, result.reason) == ("ok", 0, "")

    def test_one_failure_is_not_yet_broken(self) -> None:
        result = next_health(None, "bad hash", NOW)
        assert (result.status, result.failures, result.reason) == ("ok", 1, "bad hash")

    def test_consecutive_failures_break_it(self) -> None:
        first = next_health(None, "a", NOW)
        second = next_health(first, "b", NOW)
        assert BROKEN_AFTER == 2
        assert (second.status, second.failures, second.reason) == ("broken", 2, "b")
        assert next_health(second, "c", NOW).failures == 3

    def test_a_pass_clears_a_broken_item(self) -> None:
        broken = EntryHealth(status="broken", failures=5, checked_at=NOW, reason="x")
        cleared = next_health(broken, None, NOW)
        assert (cleared.status, cleared.failures) == ("ok", 0)


class TestParseReport:
    def test_reads_a_valid_report(self) -> None:
        parsed = parse_report(report())
        assert parsed is not None
        assert parsed.entries["connection-type/github"].status == "broken"

    def test_skips_an_entry_it_cannot_read_and_ignores_new_keys(self) -> None:
        stamp = NOW.isoformat()
        entries = {
            "connection-type/a": {"status": "ok", "failures": 0, "checked_at": stamp, "later": 1},
            "connection-type/b": {"status": "weird", "failures": 0, "checked_at": stamp},
            "connection-type/c": "nope",
        }
        parsed = parse_report(report(entries))
        assert parsed is not None
        assert set(parsed.entries) == {"connection-type/a"}

    @pytest.mark.parametrize(
        "raw",
        [
            b"{",
            b"[]",
            b"null",
            report(schema_version=2),
            report(generated_at="yesterday"),
            b'{"schema_version": 1}',
        ],
    )
    def test_anything_else_is_none(self, raw: bytes) -> None:
        assert parse_report(raw) is None


async def test_a_report_is_fetched_once_and_cached() -> None:
    host, clock = Host(report()), Clock()
    source = host.source(clock)
    first = await source.statuses()
    clock.now += TTL_SECONDS - 1
    assert await source.statuses() == first
    assert host.requests == ["/branch/health.json"]
    clock.now += 2
    await source.statuses()
    assert len(host.requests) == 2


async def test_no_url_means_no_news() -> None:
    assert await HealthSource("").statuses() == {}


@pytest.mark.parametrize("body", [None, b"{", b"[]"])
async def test_a_missing_or_bad_report_means_no_news(body: bytes | None) -> None:
    assert await Host(body).source(Clock()).statuses() == {}


async def test_an_unreachable_host_means_no_news_and_is_not_hammered() -> None:
    host, clock = Host(report()), Clock()
    host.down = True
    source = host.source(clock)
    for _ in range(3):
        assert await source.statuses() == {}
    assert len(host.requests) == 1
    clock.now += MIN_REFRESH_SECONDS + 1
    host.down = False
    assert "connection-type/github" in await source.statuses()


async def test_the_last_good_report_survives_a_failed_refresh() -> None:
    host, clock = Host(report()), Clock()
    source = host.source(clock)
    await source.statuses()
    host.down = True
    clock.now += TTL_SECONDS + 1
    assert "connection-type/github" in await source.statuses()


async def test_a_report_from_a_job_that_stopped_running_is_ignored() -> None:
    too_old = NOW + MAX_AGE + timedelta(seconds=1)
    assert await Host(report()).source(Clock(), now=too_old).statuses() == {}
    assert await Host(report()).source(Clock(), now=NOW + MAX_AGE).statuses() != {}


async def test_a_local_folder_works_too(tmp_path: Path) -> None:
    (tmp_path / "health.json").write_bytes(report())
    assert "connection-type/github" in await HealthSource(str(tmp_path)).statuses()
