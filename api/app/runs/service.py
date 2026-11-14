"""Run use cases. Reads flows through the flows service; flows never import runs."""

import base64
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol

from app.engine.compiler import compile_graph
from app.engine.inputs import InputValidationError
from app.engine.observer import Observer
from app.engine.runtime import run_flow
from app.engine.validate import parse_graph
from app.errors import ApiError
from app.flows.models import Flow
from app.flows.service import invalid_flow, not_found
from app.runs.models import Run
from app.runs.store import FlowGone, RunStore
from app.workspaces.schemas import Member


class TracingObserver(Observer, Protocol):
    trace_id: str | None


ObserverFactory = Callable[[str], TracingObserver]


async def run_draft(
    store: RunStore,
    member: Member,
    flow: Flow,
    payload: dict[str, Any],
    new_observer: ObserverFactory,
    timeout_seconds: float = 0,
    max_nodes: int = 0,
    max_edges: int = 0,
) -> Run:
    graph, issues = parse_graph(flow.draft, max_nodes, max_edges)
    if graph is None:
        raise invalid_flow(issues)
    observer = new_observer(flow.name)
    try:
        result = await run_flow(compile_graph(graph), payload, observer, timeout_seconds)
    except InputValidationError as exc:
        first = exc.issues[0]
        raise ApiError(
            422,
            "invalid_input",
            str(exc),
            {"field": first.field, "errors": [i.model_dump() for i in exc.issues]},
        ) from exc
    run = Run(
        flow_id=flow.id,
        workspace_id=member.workspace_id,
        created_by=member.user_id,
        status=result.status,
        test=True,
        input=payload,
        output=result.output,
        error=result.error.model_dump() if result.error else None,
        duration_ms=result.duration_ms,
        mlflow_trace_id=observer.trace_id,
    )
    try:
        return await store.add_run(run)
    except FlowGone:
        raise not_found("Flow") from None


def encode_cursor(run: Run) -> str:
    raw = f"{run.started_at.isoformat()}|{run.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        started_at, run_id = raw.split("|")
        return datetime.fromisoformat(started_at), uuid.UUID(run_id)
    except ValueError:
        raise ApiError(422, "invalid_cursor", "cursor is not valid") from None


async def list_runs(
    store: RunStore,
    member: Member,
    *,
    flow_id: uuid.UUID | None,
    status: str | None,
    test: bool | None,
    started_from: datetime | None,
    started_to: datetime | None,
    cursor: str | None,
    limit: int,
) -> tuple[list[Run], str | None]:
    after = decode_cursor(cursor) if cursor else None
    # one extra row tells us whether another page exists
    rows = await store.list_runs(
        member, flow_id, status, test, started_from, started_to, after, limit + 1
    )
    page = rows[:limit]
    return page, encode_cursor(page[-1]) if len(rows) > limit else None
