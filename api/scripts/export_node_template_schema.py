"""Write the JSON Schema of a node template file, so authors and CI can validate against it."""

import json
from pathlib import Path

from app.node_templates.schemas import NodeTemplate

OUTPUT = (
    Path(__file__).resolve().parents[2] / "marketplace" / "schemas" / "node-template.schema.json"
)


def schema_text() -> str:
    return json.dumps(NodeTemplate.model_json_schema(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    OUTPUT.write_text(schema_text(), encoding="utf-8", newline="\n")
