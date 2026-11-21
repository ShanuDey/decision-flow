from datetime import datetime

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


class InstallResult(FrozenBaseModel):
    # The requested item first, then anything installed with it because it needs it.
    installed: list[InstalledSummary]


class CatalogListing(FrozenBaseModel):
    entries: list[IndexEntry]
    fetched_at: datetime
    # True when the latest refresh failed and these entries are the previous copy.
    stale: bool


class CatalogReadme(FrozenBaseModel):
    markdown: str
