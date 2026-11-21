"""Nightly health of catalog items: what the nightly job writes and what the app reads."""

import asyncio
import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Annotated, Literal

import httpx
from fastapi import Depends
from pydantic import ConfigDict, ValidationError

from app.catalog.fetcher import CatalogUnavailable, Fetcher, build_fetcher
from app.engine.base import FrozenBaseModel
from app.settings import Settings, get_settings

logger = logging.getLogger("uvicorn.error")

SCHEMA_VERSION = 1
BROKEN_AFTER = 2
TTL_SECONDS = 300.0
MIN_REFRESH_SECONDS = 30.0
MAX_BYTES = 256 * 1024
# A report from a nightly job that stopped running says nothing about today.
MAX_AGE = timedelta(days=3)

Status = Literal["ok", "broken"]


class EntryHealth(FrozenBaseModel):
    status: Status
    # Nightly runs in a row that failed; an item is only broken after BROKEN_AFTER of them.
    failures: int
    checked_at: datetime
    reason: str = ""


class HealthReport(FrozenBaseModel):
    schema_version: Literal[1] = SCHEMA_VERSION
    generated_at: datetime
    # Keyed by `<kind>/<id>`, like an index entry's `requires`.
    entries: dict[str, EntryHealth]


class _PublishedEntry(EntryHealth):
    model_config = ConfigDict(extra="ignore")


def next_health(previous: EntryHealth | None, failure: str | None, now: datetime) -> EntryHealth:
    if failure is None:
        return EntryHealth(status="ok", failures=0, checked_at=now)
    failures = (previous.failures if previous else 0) + 1
    status: Status = "broken" if failures >= BROKEN_AFTER else "ok"
    return EntryHealth(status=status, failures=failures, checked_at=now, reason=failure)


def parse_report(raw: bytes) -> HealthReport | None:
    """None when the file is not a report this app understands; odd entries are skipped."""
    try:
        document = json.loads(raw)
        if not isinstance(document, dict) or document.get("schema_version") != SCHEMA_VERSION:
            return None
        entries: dict[str, EntryHealth] = {}
        for key, value in document["entries"].items():
            try:
                entries[str(key)] = EntryHealth(
                    **_PublishedEntry.model_validate(value).model_dump()
                )
            except ValidationError:
                continue
        return HealthReport(
            generated_at=datetime.fromisoformat(document["generated_at"]), entries=entries
        )
    except (ValueError, KeyError, AttributeError, TypeError):
        return None


class HealthSource:
    """The latest report, cached. It never raises: no news is treated as every item being fine."""

    def __init__(
        self,
        url: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.url = url.strip().rstrip("/")
        self._transport = transport
        self._clock = clock
        self._now = now
        self._fetcher: Fetcher | None = None
        self._lock = asyncio.Lock()
        self._report: HealthReport | None = None
        self._attempted = float("-inf")

    async def aclose(self) -> None:
        if self._fetcher is not None:
            await self._fetcher.aclose()
            self._fetcher = None

    async def statuses(self) -> dict[str, EntryHealth]:
        if not self.url:
            return {}
        async with self._lock:
            now = self._clock()
            if now - self._attempted >= (TTL_SECONDS if self._report else MIN_REFRESH_SECONDS):
                self._attempted = now
                await self._refresh()
        report = self._report
        if report is None or self._now() - report.generated_at > MAX_AGE:
            return {}
        return report.entries

    async def _refresh(self) -> None:
        try:
            if self._fetcher is None:
                self._fetcher = build_fetcher(self.url, self._transport)
            raw = await self._fetcher.get("health.json", MAX_BYTES, missing_ok=True)
        except CatalogUnavailable as exc:
            logger.warning("catalog health unavailable: %s", exc)
            return
        report = parse_report(raw) if raw is not None else None
        if report is not None:
            self._report = report


@lru_cache
def _source_for(url: str) -> HealthSource:
    return HealthSource(url)


def get_health_source(settings: Annotated[Settings, Depends(get_settings)]) -> HealthSource:
    return _source_for(settings.effective_catalog_health_url)
