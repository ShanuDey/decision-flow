"""Write the catalog index that the Marketplace will list from."""

import json
from pathlib import Path

from app.catalog.index import build_index

OUTPUT = Path(__file__).resolve().parents[1] / "app" / "catalog" / "index.json"


def index_text() -> str:
    return json.dumps(build_index().model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    OUTPUT.write_text(index_text(), encoding="utf-8", newline="\n")
