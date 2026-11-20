"""Write the catalog index that the Marketplace lists from."""

import json
from pathlib import Path

from app.catalog.index import build_index
from app.catalog.source import load_files

MARKETPLACE = Path(__file__).resolve().parents[2] / "marketplace"
OUTPUT = MARKETPLACE / "index.json"


def index_text(root: Path = MARKETPLACE) -> str:
    index = build_index(load_files(root / "catalog"))
    return json.dumps(index.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    OUTPUT.write_text(index_text(), encoding="utf-8", newline="\n")
