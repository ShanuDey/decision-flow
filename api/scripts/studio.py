"""Entry point for `langgraph dev` (LangGraph Studio): the compiled example flows."""

import json
from pathlib import Path

from app.engine.compiler import compile_graph
from app.engine.validate import parse_graph

FLOWS = Path(__file__).resolve().parents[2] / "examples" / "flows"


def _load(name: str):
    graph, issues = parse_graph(json.loads((FLOWS / f"{name}.json").read_text()))
    if graph is None:
        raise ValueError(f"{name}: {issues}")
    return compile_graph(graph).graph


start_end = _load("start-end")
