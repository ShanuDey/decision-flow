from functools import lru_cache
from pathlib import Path

from app.engine.graph import Graph
from app.engine.nodes import NODE_TYPES
from app.flows.schemas import FlowFormat, FlowFormatExample
from app.templates.service import load_templates

GUIDE = Path(__file__).with_name("format_guide.md")


@lru_cache(maxsize=1)
def flow_format() -> FlowFormat:
    return FlowFormat(
        guide=GUIDE.read_text(encoding="utf-8"),
        node_types=[node.type_name() for node in NODE_TYPES],
        graph_schema=Graph.model_json_schema(),
        examples=[
            FlowFormatExample(id=t.id, title=t.title, summary=t.summary, draft=t.draft)
            for t in load_templates()
        ],
    )
