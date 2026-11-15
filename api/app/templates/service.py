import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.engine.validate import parse_graph
from app.templates.schemas import Template

DATA = Path(__file__).parent / "data"


def _names(nodes: list[dict[str, Any]], node_type: str, key: str) -> list[str]:
    return [
        item["name"]
        for node in nodes
        if node["type"] == node_type
        for item in node.get("data", {}).get(key, [])
    ]


def _build(raw: dict[str, Any]) -> Template:
    draft = raw["draft"]
    _, issues = parse_graph(draft)
    if issues:
        raise ValueError(f"template {raw['id']} is invalid: {issues}")
    nodes = draft["nodes"]
    return Template(
        id=raw["id"],
        title=raw["title"],
        summary=raw["summary"],
        description=raw["description"],
        category=raw["category"],
        inputs=_names(nodes, "start", "inputs"),
        outputs=_names(nodes, "end", "outputs"),
        node_types=sorted({node["type"] for node in nodes}),
        draft=draft,
    )


@lru_cache(maxsize=1)
def load_templates() -> tuple[Template, ...]:
    templates = tuple(_build(json.loads(p.read_text())) for p in sorted(DATA.glob("*.json")))
    ids = [t.id for t in templates]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate template id")
    return templates
