"""Loads the connection types shipped with the app from their JSON files."""

import json
from pathlib import Path

from pydantic import ValidationError

from app.connections.types import ConnectionType

DATA = Path(__file__).parent / "data"


def load_types(directory: Path = DATA) -> list[ConnectionType]:
    """Raises ValueError naming the file when one is malformed, so a bad file stops startup."""
    found: dict[str, ConnectionType] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            kind = ConnectionType.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (ValueError, ValidationError) as exc:
            raise ValueError(f"{path.name}: {exc}") from None
        if kind.id in found:
            raise ValueError(f"{path.name}: the id '{kind.id}' is already used")
        found[kind.id] = kind
    return sorted(found.values(), key=lambda t: (t.category != "builtin", t.name))


TYPES = load_types()
BY_ID = {t.id: t for t in TYPES}
