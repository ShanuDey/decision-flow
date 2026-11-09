"""Run use cases. Reads flows through the flows service; flows never import runs."""

from collections.abc import Callable
from typing import Any, Protocol

from app.engine.compiler import compile_graph
from app.engine.inputs import InputValidationError
from app.engine.observer import Observer
from app.engine.runtime import run_flow
from app.engine.validate import parse_graph
from app.errors import ApiError
from app.flows.models import Flow
from app.flows.service import invalid_flow
from app.runs.models import Run
from app.runs.store import RunStore


class TracingObserver(Observer, Protocol):
    trace_id: str | None


ObserverFactory = Callable[[str], TracingObserver]


async def run_draft(
    store: RunStore, flow: Flow, payload: dict[str, Any], new_observer: ObserverFactory
) -> Run:
    graph, issues = parse_graph(flow.draft)
    if graph is None:
        raise invalid_flow(issues)
    observer = new_observer(flow.name)
    try:
        result = await run_flow(compile_graph(graph), payload, observer)
    except InputValidationError as exc:
        first = exc.issues[0]
        raise ApiError(
            422,
            "invalid_input",
            str(exc),
            {"field": first.field, "errors": [i.model_dump() for i in exc.issues]},
        ) from exc
    return await store.add_run(
        Run(
            flow_id=flow.id,
            status=result.status,
            test=True,
            input=payload,
            output=result.output,
            error=result.error.model_dump() if result.error else None,
            duration_ms=result.duration_ms,
            mlflow_trace_id=observer.trace_id,
        )
    )
