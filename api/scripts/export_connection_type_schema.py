"""Write the JSON Schema of a connection type file, so authors and CI can validate against it."""

import json
from pathlib import Path

from app.connections.types import ConnectionType

OUTPUT = Path(__file__).resolve().parents[1] / "app" / "connections" / "connection-type.schema.json"


def schema_text() -> str:
    return json.dumps(ConnectionType.model_json_schema(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    OUTPUT.write_text(schema_text(), encoding="utf-8")
