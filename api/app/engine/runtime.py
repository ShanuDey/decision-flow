"""Executes a compiled flow. No DB and no web imports: plain dicts in, a RunResult out."""

import time
from dataclasses import dataclass
from typing import Any, Literal

from app.engine.compiler import CompiledFlow
from app.engine.inputs import validate_input
from app.engine.observer import NodeError, NullObserver, Observer


@dataclass(frozen=True)
class RunError:
    node_id: str
    message: str


@dataclass(frozen=True)
class RunResult:
    status: Literal["succeeded", "failed"]
    output: dict[str, Any] | None
    error: RunError | None
    duration_ms: int


async def run_flow(
    flow: CompiledFlow, payload: dict[str, Any], observer: Observer | None = None
) -> RunResult:
    """Raises InputValidationError before anything runs; a failure inside the flow is a result."""
    inputs = validate_input(flow.start.data.inputs, payload)
    state = {
        "input": inputs,
        "vars": {v.name: v.initial for v in flow.variables},
        "nodes": {},
    }
    config = {"configurable": {"observer": observer or NullObserver()}}
    started = time.perf_counter()
    try:
        final = await flow.graph.ainvoke(state, config=config)
    except NodeError as exc:
        ms = int((time.perf_counter() - started) * 1000)
        return RunResult("failed", None, RunError(exc.node_id, exc.message), ms)
    return RunResult(
        "succeeded", final["_output"], None, int((time.perf_counter() - started) * 1000)
    )
