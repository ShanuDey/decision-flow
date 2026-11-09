import json
from pathlib import Path

import pytest

from app.engine.validate import parse_graph

FLOWS = Path(__file__).resolve().parents[2] / "examples" / "flows"


@pytest.mark.parametrize("path", sorted(FLOWS.glob("*.json")), ids=lambda p: p.name)
def test_every_example_flow_is_valid(path: Path) -> None:
    assert parse_graph(json.loads(path.read_text()))[1] == []
