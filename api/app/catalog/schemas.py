from datetime import datetime
from typing import Any, Literal

from app.catalog.flow_file import FlowConnection
from app.catalog.index import IndexEntry
from app.catalog.source import Kind
from app.engine.base import FrozenBaseModel


class InstallRequest(FrozenBaseModel):
    kind: Kind
    id: str
    version: str
    # The entry's hash from the index; the file must still match it.
    hash: str


class InstalledSummary(FrozenBaseModel):
    kind: Kind
    id: str
    name: str
    version: str
    hash: str
    installed_at: datetime


class InstalledList(FrozenBaseModel):
    items: list[InstalledSummary]


class InstalledFlow(FrozenBaseModel):
    id: str
    name: str
    description: str
    icon: str
    version: str
    inputs: list[str]
    outputs: list[str]
    # Placeholder connection ids used by the draft's request nodes, and what each one stands for.
    connections: dict[str, FlowConnection]
    draft: dict[str, Any]


class InstalledFlowList(FrozenBaseModel):
    items: list[InstalledFlow]


class InstallResult(FrozenBaseModel):
    # The requested item first, then anything installed with it because it needs it.
    installed: list[InstalledSummary]


class ListedEntry(IndexEntry):
    # From the nightly check; "broken" items cannot be installed until a later run passes.
    health: Literal["ok", "broken"] = "ok"
    health_reason: str = ""


class CatalogListing(FrozenBaseModel):
    entries: list[ListedEntry]
    fetched_at: datetime
    # True when the latest refresh failed and these entries are the previous copy.
    stale: bool


class CatalogReadme(FrozenBaseModel):
    markdown: str
