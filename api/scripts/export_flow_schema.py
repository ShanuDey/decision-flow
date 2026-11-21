"""Write the JSON Schema of a marketplace flow file, so authors and CI can validate against it."""

import json
from pathlib import Path

from app.catalog.flow_file import CatalogFlow

OUTPUT = Path(__file__).resolve().parents[2] / "marketplace" / "schemas" / "flow.schema.json"


def schema_text() -> str:
    return json.dumps(CatalogFlow.model_json_schema(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    OUTPUT.write_text(schema_text(), encoding="utf-8", newline="\n")
