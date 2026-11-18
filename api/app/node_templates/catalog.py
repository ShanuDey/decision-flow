"""Loads the node templates shipped with the app from their JSON files."""

import json
from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from app.connections.catalog import BY_ID as CONNECTION_TYPES
from app.connections.types import ConnectionType
from app.node_templates.schemas import NodeTemplate

DATA = Path(__file__).parent / "data"


def _connection_problem(template: NodeTemplate, types: Mapping[str, ConnectionType]) -> str | None:
    wanted = template.connection
    if wanted is None:
        return None
    kind = types.get(wanted.type)
    if kind is None:
        return f"connection type '{wanted.type}' does not exist"
    for name in wanted.values:
        field = kind.field(name)
        if field is None or field.secret:
            return f"connection value '{name}' is not a plain field of {kind.name}"
    return None


def load_templates(
    directory: Path = DATA, types: Mapping[str, ConnectionType] = CONNECTION_TYPES
) -> list[NodeTemplate]:
    """Raises ValueError naming the file when one is malformed, so a bad file stops startup."""
    found: dict[str, NodeTemplate] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            template = NodeTemplate.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (ValueError, ValidationError) as exc:
            raise ValueError(f"{path.name}: {exc}") from None
        if problem := _connection_problem(template, types):
            raise ValueError(f"{path.name}: {problem}")
        if template.id in found:
            raise ValueError(f"{path.name}: the id '{template.id}' is already used")
        found[template.id] = template
    return sorted(found.values(), key=lambda t: t.name)


TEMPLATES = load_templates()
BY_ID = {t.id: t for t in TEMPLATES}
