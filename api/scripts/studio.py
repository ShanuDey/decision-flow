"""Entry point for `langgraph dev` (LangGraph Studio): the valid example flows, traced by MLflow."""

import json
import sys
from pathlib import Path

from app import tracing
from app.engine.compiler import compile_graph
from app.engine.validate import parse_graph
from app.settings import get_settings

FLOWS = Path(__file__).resolve().parents[2] / "examples" / "flows"

# Studio calls graphs directly (not through run_flow), so let MLflow trace them automatically.
tracing.enable_autolog(get_settings())

# One module variable per valid flow (examples/flows/my-flow.json -> my_flow); langgraph.json
# lists the ones to serve. Invalid flows are skipped, not fatal.
for _path in sorted(FLOWS.glob("*.json")):
    try:
        _graph, _issues = parse_graph(json.loads(_path.read_text()))
    except ValueError as _exc:
        _graph, _issues = None, [_exc]
    if _graph is None:
        print(f"studio: skipping {_path.name}: {_issues}", file=sys.stderr)
        continue
    globals()[_path.stem.replace("-", "_")] = compile_graph(_graph).graph
