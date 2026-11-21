"""Marketplace use cases: what a workspace has installed, installing, removing. No HTTP types."""

from typing import cast

from pydantic import ValidationError

from app.catalog.index import IndexEntry, file_hash
from app.catalog.models import InstalledItem
from app.catalog.remote import (
    CatalogItemInvalid,
    CatalogItemMissing,
    CatalogSource,
    CatalogUnavailable,
    Listing,
)
from app.catalog.schemas import (
    CatalogListing,
    InstalledList,
    InstalledSummary,
    InstallRequest,
    InstallResult,
)
from app.catalog.source import CatalogFile, Kind
from app.catalog.store import InstalledStore, ItemDraft
from app.connections.catalog import BY_ID as BUILT_IN_TYPES
from app.connections.store import ConnectionStore
from app.connections.types import ConnectionType
from app.errors import ApiError
from app.node_templates.catalog import connection_problem
from app.node_templates.schemas import NodeTemplate
from app.workspaces.schemas import Member


def summarize(item: InstalledItem) -> InstalledSummary:
    return InstalledSummary(
        kind=cast(Kind, item.kind),
        id=item.item_id,
        name=str(item.definition.get("name", item.item_id)),
        version=item.version,
        hash=item.hash,
        installed_at=item.installed_at,
    )


async def list_installed(store: InstalledStore, member: Member) -> InstalledList:
    return InstalledList(items=[summarize(i) for i in await store.list_items(member)])


def _types_of(items: list[InstalledItem]) -> dict[str, ConnectionType]:
    found: dict[str, ConnectionType] = {}
    for item in items:
        try:
            found[item.item_id] = ConnectionType.model_validate(item.definition)
        except ValidationError:
            continue  # a stored copy the app no longer understands is skipped, not fatal
    return found


async def connection_types(store: InstalledStore, member: Member) -> dict[str, ConnectionType]:
    """Every connection type this workspace can use: built-in plus installed."""
    installed = _types_of(await store.list_items(member, "connection-type"))
    return {**installed, **BUILT_IN_TYPES}


async def installed_templates(store: InstalledStore, member: Member) -> list[NodeTemplate]:
    found: list[NodeTemplate] = []
    for item in await store.list_items(member, "node-template"):
        try:
            found.append(NodeTemplate.model_validate(item.definition))
        except ValidationError:
            continue
    return found


def _draft(file: CatalogFile) -> ItemDraft:
    return ItemDraft(
        kind=file.kind,
        item_id=file.id,
        version=file.version,
        hash=file_hash(file),
        definition=file.body.model_dump(mode="json"),
    )


def _listing(listing: Listing) -> CatalogListing:
    return CatalogListing(
        entries=listing.index.entries, fetched_at=listing.fetched_at, stale=listing.stale
    )


def _unavailable(exc: CatalogUnavailable) -> ApiError:
    return ApiError(
        503,
        "catalog_unavailable",
        str(exc),
        {"disabled": True} if exc.disabled else {},
    )


async def catalog_listing(source: CatalogSource, *, force: bool = False) -> CatalogListing:
    try:
        return _listing(await source.index(force=force))
    except CatalogUnavailable as exc:
        raise _unavailable(exc) from None


def _stale_entry() -> ApiError:
    return ApiError(
        409,
        "hash_mismatch",
        "The catalog entry changed since you loaded it; refresh the Marketplace and try again",
    )


async def _fetch(source: CatalogSource, entry: IndexEntry) -> CatalogFile:
    """The one file behind an index entry, checked against the entry's hash."""
    try:
        file = await source.read(entry.kind, entry.id, entry.version)
    except CatalogItemMissing:
        raise ApiError(404, "catalog_item_not_found", "That catalog entry does not exist") from None
    except CatalogItemInvalid as exc:
        raise ApiError(422, "invalid_catalog_item", str(exc)) from None
    except CatalogUnavailable as exc:
        raise _unavailable(exc) from None
    if file_hash(file) != entry.hash:
        raise _stale_entry()
    return file


def _missing_requirements(
    entry: IndexEntry, listed: dict[str, IndexEntry], have: set[str]
) -> list[IndexEntry]:
    missing: list[IndexEntry] = []
    for need in entry.requires:
        if need in have:
            continue
        if need not in listed:
            raise ApiError(409, "requirement_missing", f"The catalog has no {need}")
        missing.append(listed[need])
    return missing


async def install(
    store: InstalledStore, source: CatalogSource, member: Member, request: InstallRequest
) -> InstallResult:
    """Fetches and checks everything first, then writes the item and what it needs together."""
    listed = {f"{e.kind}/{e.id}": e for e in (await catalog_listing(source)).entries}
    entry = listed.get(f"{request.kind}/{request.id}")
    if entry is None:
        raise ApiError(404, "catalog_item_not_found", "That catalog entry does not exist")
    if (entry.version, entry.hash) != (request.version, request.hash):
        raise _stale_entry()

    have = {f"{i.kind}/{i.item_id}" for i in await store.list_items(member)}
    needs = _missing_requirements(entry, listed, have)
    files = [await _fetch(source, e) for e in (*needs, entry)]
    *required, file = files

    if isinstance(file.body, NodeTemplate):
        types = {
            **await connection_types(store, member),
            **{f.id: f.body for f in required if isinstance(f.body, ConnectionType)},
        }
        if problem := connection_problem(file.body, types):
            raise ApiError(422, "invalid_catalog_item", problem)

    saved = await store.put_all(member, [_draft(f) for f in files])
    *also, item = saved
    return InstallResult(installed=[summarize(item), *(summarize(i) for i in also)])


async def uninstall(
    store: InstalledStore,
    connections: ConnectionStore,
    member: Member,
    kind: Kind,
    item_id: str,
) -> None:
    if await store.get(member, kind, item_id) is None:
        raise ApiError(404, "not_found", "That item is not installed")
    if kind == "connection-type":
        used = await connections.count_by_type(member, item_id)
        if used:
            raise ApiError(
                409,
                "type_in_use",
                f"{used} connection{'s' if used != 1 else ''} use this type; delete them first",
                {"count": used},
            )
        needing = [
            t.name
            for t in await installed_templates(store, member)
            if t.connection and t.connection.type == item_id
        ]
        if needing:
            raise ApiError(
                409,
                "required_by",
                f"Installed templates need this type: {', '.join(needing)}",
                {"names": needing},
            )
    await store.delete(member, kind, item_id)
