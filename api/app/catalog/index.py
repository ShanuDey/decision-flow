"""The marketplace index: summaries a browser can list without fetching the files."""

import hashlib
import json
from typing import Literal

from app.catalog.flow_file import CatalogFlow
from app.catalog.source import CatalogFile, Kind, latest
from app.connections.types import ConnectionType
from app.engine.base import FrozenBaseModel
from app.node_templates.schemas import NodeTemplate


class IndexEntry(FrozenBaseModel):
    id: str
    kind: Kind
    name: str
    description: str
    icon: str
    tags: list[str]
    version: str
    # sha256 of the validated file with defaults filled in; installers hash it with `content_hash`.
    hash: str
    # Where the file lives under the catalog root; versioned, so a published file never changes.
    path: str
    # Other entries this one needs, as `<kind>/<id>`; installing it installs them first.
    requires: list[str]
    has_readme: bool


class CatalogIndex(FrozenBaseModel):
    schema_version: Literal[1] = 1
    entries: list[IndexEntry]


def content_hash(body: dict[str, object]) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256-" + hashlib.sha256(canonical.encode()).hexdigest()


def file_hash(file: CatalogFile) -> str:
    return content_hash(file.body.model_dump(mode="json"))


def _entry(file: CatalogFile, catalog_types: set[str]) -> IndexEntry:
    """An item requires the connection types it uses when those types are also in the catalog."""
    body = file.body
    tags = body.tags if isinstance(body, NodeTemplate | CatalogFlow) else []
    wanted: list[str] = []
    if isinstance(body, NodeTemplate) and body.connection:
        wanted = [body.connection.type]
    elif isinstance(body, CatalogFlow):
        wanted = sorted({c.type for c in body.connections.values()})
    requires = [f"connection-type/{t}" for t in wanted if t in catalog_types]
    return IndexEntry(
        id=file.id,
        kind=file.kind,
        name=body.name,
        description=body.description,
        icon=body.icon,
        tags=tags,
        version=file.version,
        hash=file_hash(file),
        path=file.path,
        requires=requires,
        has_readme=file.has_readme,
    )


def build_index(files: list[CatalogFile]) -> CatalogIndex:
    newest = latest(files)
    catalog_types = {f.id for f in newest if isinstance(f.body, ConnectionType)}
    return CatalogIndex(entries=[_entry(f, catalog_types) for f in newest])
