"""Catalog files: their shapes, parsing, and loading a catalog folder from disk."""

import json
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from app.connections.catalog import BY_ID as BUILT_IN_TYPES
from app.connections.types import ConnectionType
from app.engine.base import FrozenBaseModel
from app.node_templates.catalog import BY_ID as BUILT_IN_TEMPLATES
from app.node_templates.catalog import connection_problem
from app.node_templates.schemas import NodeTemplate

Kind = Literal["connection-type", "node-template"]
DIRECTORIES: dict[Kind, str] = {
    "connection-type": "connection-types",
    "node-template": "node-templates",
}


class CatalogFile(FrozenBaseModel):
    kind: Kind
    id: str
    version: str
    # Under the catalog root; the file is immutable once published.
    path: str
    body: ConnectionType | NodeTemplate
    has_readme: bool = False


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def parse_file(kind: Kind, text: str) -> ConnectionType | NodeTemplate:
    raw = json.loads(text)
    return (ConnectionType if kind == "connection-type" else NodeTemplate).model_validate(raw)


def load_files(root: Path) -> list[CatalogFile]:
    """Raises ValueError naming the file when one is malformed, so a bad file stops startup."""
    found: list[CatalogFile] = []
    for kind, directory in DIRECTORIES.items():
        for path in sorted((root / directory).glob("*/*.json")):
            relative = path.relative_to(root).as_posix()
            try:
                body = parse_file(kind, path.read_text(encoding="utf-8"))
            except (ValueError, ValidationError) as exc:
                raise ValueError(f"{relative}: {exc}") from None
            if body.id != path.parent.name or f"{body.version}.json" != path.name:
                raise ValueError(f"{relative}: the path must be <id>/<version>.json")
            found.append(
                CatalogFile(
                    kind=kind,
                    id=body.id,
                    version=body.version,
                    path=relative,
                    body=body,
                    has_readme=(path.parent / "README.md").is_file(),
                )
            )

    for file in found:
        built_in = BUILT_IN_TYPES if file.kind == "connection-type" else BUILT_IN_TEMPLATES
        if file.id in built_in:
            raise ValueError(f"{file.path}: '{file.id}' is a built-in id and cannot be reused")

    types = {
        **BUILT_IN_TYPES,
        **{f.id: f.body for f in found if isinstance(f.body, ConnectionType)},
    }
    for file in found:
        if isinstance(file.body, NodeTemplate) and (
            problem := connection_problem(file.body, types)
        ):
            raise ValueError(f"{file.path}: {problem}")
    return found


def latest(files: list[CatalogFile]) -> list[CatalogFile]:
    """The newest version of each item; older files stay readable for pinned installs."""
    newest: dict[tuple[str, str], CatalogFile] = {}
    for file in files:
        key = (file.kind, file.id)
        if key not in newest or _version_key(file.version) > _version_key(newest[key].version):
            newest[key] = file
    return sorted(newest.values(), key=lambda f: (f.kind, f.body.name))
