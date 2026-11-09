"""Executes a compiled flow. No DB and no web imports: plain dicts in, a RunResult out."""

import time
from typing import Any, Literal

from app.engine.base import FrozenBaseModel
from app.engine.compiler import CompiledFlow
from app.engine.inputs import validate_input
from app.engine.observer import NodeError, NullObserver, Observer


class RunError(FrozenBaseModel):
    node_id: str
    message: str


class RunResult(FrozenBaseModel):
    status: Literal["succeeded", "failed"]
    output: dict[str, Any] | None
    error: RunError | None
    duration_ms: int


async def run_flow(
    flow: CompiledFlow, payload: dict[str, Any], observer: Observer | None = None
) -> RunResult:
    """Raises InputValidationError before anything runs; a failure inside the flow is a result."""
    inputs = validate_input(flow.start.data.inputs, payload)
    state = {"input": inputs}
    observer = observer or NullObserver()
    config = {"configurable": {"observer": observer}}
    await observer.run_started(inputs)
    started = time.perf_counter()
    try:
        final = await flow.graph.ainvoke(state, config=config)
    except NodeError as exc:
        ms = int((time.perf_counter() - started) * 1000)
        await observer.run_finished("failed", str(exc))
        return RunResult(
            status="failed",
            output=None,
            error=RunError(node_id=exc.node_id, message=exc.message),
            duration_ms=ms,
        )
    ms = int((time.perf_counter() - started) * 1000)
    await observer.run_finished("succeeded", None, final["_output"])
    return RunResult(status="succeeded", output=final["_output"], error=None, duration_ms=ms)
