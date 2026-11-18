"""One index over everything the app ships: summaries a browser can list without the files."""

import hashlib
import json
from typing import Literal

from app.connections.catalog import TYPES
from app.engine.base import FrozenBaseModel
from app.node_templates.catalog import TEMPLATES

Kind = Literal["connection-type", "node-template"]
DIRECTORIES: dict[Kind, str] = {
    "connection-type": "connection-types",
    "node-template": "node-templates",
}


class IndexEntry(FrozenBaseModel):
    id: str
    kind: Kind
    name: str
    description: str
    tags: list[str]
    version: str
    # sha256 of the validated file with defaults filled in; installers hash it with `content_hash`.
    hash: str
    # Where the file lives under the catalog root; versioned, so a published file never changes.
    path: str


class Index(FrozenBaseModel):
    schema_version: Literal[1] = 1
    entries: list[IndexEntry]


def content_hash(body: dict[str, object]) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256-" + hashlib.sha256(canonical.encode()).hexdigest()


def build_index() -> Index:
    entries = [
        IndexEntry(
            id=t.id,
            kind="connection-type",
            name=t.name,
            description=t.description,
            tags=[t.category],
            version=t.version,
            hash=content_hash(t.model_dump(mode="json")),
            path=f"{DIRECTORIES['connection-type']}/{t.id}/{t.version}.json",
        )
        for t in TYPES
    ] + [
        IndexEntry(
            id=t.id,
            kind="node-template",
            name=t.name,
            description=t.description,
            tags=t.tags,
            version=t.version,
            hash=content_hash(t.model_dump(mode="json")),
            path=f"{DIRECTORIES['node-template']}/{t.id}/{t.version}.json",
        )
        for t in TEMPLATES
    ]
    return Index(entries=entries)
