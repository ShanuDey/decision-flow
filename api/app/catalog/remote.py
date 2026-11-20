"""The Marketplace catalog as the app sees it: a cached index and validated item files."""

import asyncio
import json
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends
from pydantic import ConfigDict, ValidationError

from app.catalog.fetcher import CatalogUnavailable, Fetcher, build_fetcher
from app.catalog.index import CatalogIndex, IndexEntry
from app.catalog.source import DIRECTORIES, CatalogFile, Kind, parse_file
from app.connections.catalog import BY_ID as BUILT_IN_TYPES
from app.engine.base import FrozenBaseModel
from app.node_templates.schemas import NodeTemplate
from app.settings import Settings, get_settings

TTL_SECONDS = 300.0
MIN_REFRESH_SECONDS = 30.0
MAX_FILE_BYTES = 256 * 1024
MAX_INDEX_BYTES = 1024 * 1024

ID = re.compile(r"[a-z][a-z0-9_]*")
VERSION = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")

__all__ = ["CatalogUnavailable"]


class CatalogItemMissing(Exception):
    pass


class CatalogItemInvalid(Exception):
    pass


class _PublishedEntry(IndexEntry):
    """An index entry as published: keys a newer catalog added are ignored, not fatal."""

    model_config = ConfigDict(extra="ignore")


class Listing(FrozenBaseModel):
    index: CatalogIndex
    fetched_at: datetime
    stale: bool


def parse_index(raw: bytes) -> CatalogIndex:
    """Entries this app cannot read are skipped, so one odd entry never hides the rest."""
    try:
        document = json.loads(raw)
    except ValueError:
        document = None
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != CatalogIndex.model_fields["schema_version"].default
        or not isinstance(document.get("entries"), list)
    ):
        raise CatalogUnavailable("The catalog index is not valid")
    entries: list[IndexEntry] = []
    for item in document["entries"]:
        try:
            entries.append(IndexEntry(**_PublishedEntry.model_validate(item).model_dump()))
        except ValidationError:
            continue
    return CatalogIndex(entries=entries)


class CatalogSource:
    """Caches the index (stale-if-error) and reads single files through a Fetcher."""

    def __init__(
        self,
        url: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.url = url.strip().rstrip("/")
        self._transport = transport
        self._clock = clock
        self._fetcher: Fetcher | None = None
        self._lock = asyncio.Lock()
        self._cached: CatalogIndex | None = None
        self._fetched_at = datetime.now(UTC)
        self._fetched_mono = 0.0
        self._attempted = float("-inf")
        self._failure: CatalogUnavailable | None = None
        self._stale = False

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    async def aclose(self) -> None:
        if self._fetcher is not None:
            await self._fetcher.aclose()
            self._fetcher = None

    def _listing(self) -> Listing:
        assert self._cached is not None
        return Listing(index=self._cached, fetched_at=self._fetched_at, stale=self._stale)

    async def index(self, *, force: bool = False) -> Listing:
        """The index, cached; a failed refresh serves the previous copy marked stale."""
        if not self.enabled:
            raise CatalogUnavailable(
                "The Marketplace is switched off on this server", disabled=True
            )
        async with self._lock:
            now = self._clock()
            recently_tried = now - self._attempted < MIN_REFRESH_SECONDS
            if self._cached is None:
                if recently_tried and self._failure is not None:
                    raise self._failure
            elif recently_tried or not (force or now - self._fetched_mono >= TTL_SECONDS):
                return self._listing()
            return await self._refresh(now)

    async def _refresh(self, now: float) -> Listing:
        self._attempted = now
        try:
            raw = await self._fetch().get("index.json", MAX_INDEX_BYTES)
            if raw is None:
                raise CatalogUnavailable("The catalog has no index")
            loaded = parse_index(raw)
        except CatalogUnavailable as exc:
            self._failure = exc
            if self._cached is None:
                raise
            self._stale = True
            return self._listing()
        self._cached, self._stale, self._failure = loaded, False, None
        self._fetched_mono, self._fetched_at = now, datetime.now(UTC)
        return self._listing()

    async def read(self, kind: Kind, item_id: str, version: str) -> CatalogFile:
        """One catalog file. The path is built here from checked parts, never taken from input."""
        if not ID.fullmatch(item_id) or not VERSION.fullmatch(version):
            raise CatalogItemMissing
        listing = await self.index()
        path = f"{DIRECTORIES[kind]}/{item_id}/{version}.json"
        raw = await self._fetch().get(f"catalog/{path}", MAX_FILE_BYTES, missing_ok=True)
        if raw is None:
            raise CatalogItemMissing
        try:
            body = parse_file(kind, raw.decode("utf-8"))
        except (ValueError, ValidationError) as exc:
            raise CatalogItemInvalid(f"{path}: {exc}") from None
        if (body.id, body.version) != (item_id, version):
            raise CatalogItemInvalid(f"{path}: the file's id and version do not match its path")
        if isinstance(body, NodeTemplate) and body.connection:
            wanted = body.connection.type
            known = {e.id for e in listing.index.entries if e.kind == "connection-type"}
            if wanted not in BUILT_IN_TYPES and wanted not in known:
                raise CatalogItemInvalid(f"connection type '{wanted}' does not exist")
        return CatalogFile(kind=kind, id=item_id, version=version, path=path, body=body)

    def _fetch(self) -> Fetcher:
        if self._fetcher is None:
            self._fetcher = build_fetcher(self.url, self._transport)
        return self._fetcher


@lru_cache
def _source_for(url: str) -> CatalogSource:
    return CatalogSource(url)


def get_catalog_source(settings: Annotated[Settings, Depends(get_settings)]) -> CatalogSource:
    return _source_for(settings.catalog_url)
