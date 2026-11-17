"""Run use cases. Reads flows through the flows service; flows never import runs."""

import base64
import uuid
from collections.abc import Awaitable, Callable, Collection
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from app.engine.compiler import compile_graph
from app.engine.inputs import InputValidationError
from app.engine.observer import Observer
from app.engine.run_secrets import RunSecrets, referenced_secret_names
from app.engine.runtime import run_flow
from app.engine.validate import parse_graph
from app.errors import ApiError
from app.flows.models import Flow, FlowVersion
from app.flows.service import invalid_flow, not_found
from app.flows.subflows import SubflowSource
from app.runs.models import Run
from app.runs.schemas import RunSteps
from app.runs.steps import build_steps
from app.runs.store import FlowGone, RunStore
from app.security.ssrf import OutboundPolicy
from app.tracing import TraceSpan, TraceUnavailable
from app.workspaces.schemas import Member


class TracingObserver(Observer, Protocol):
    trace_id: str | None


SecretLoader = Callable[[set[str]], Awaitable[RunSecrets]]
ObserverFactory = Callable[[str], TracingObserver]
TraceReader = Callable[[str], Awaitable[list[TraceSpan] | None]]

TRACE_GRACE = timedelta(seconds=60)


async def run_draft(
    store: RunStore,
    member: Member,
    flow: Flow,
    payload: dict[str, Any],
    new_observer: ObserverFactory,
    load_secrets: SecretLoader,
    timeout_seconds: float = 0,
    max_nodes: int = 0,
    max_edges: int = 0,
    disabled_types: Collection[str] = (),
    outbound: OutboundPolicy | None = None,
    subflows: SubflowSource | None = None,
) -> Run:
    return await _run(
        store,
        member,
        flow,
        flow.draft,
        None,
        payload,
        new_observer,
        load_secrets,
        timeout_seconds,
        max_nodes,
        max_edges,
        disabled_types,
        outbound,
        subflows,
    )


async def run_published(
    store: RunStore,
    member: Member,
    flow: Flow,
    version: FlowVersion,
    payload: dict[str, Any],
    new_observer: ObserverFactory,
    load_secrets: SecretLoader,
    timeout_seconds: float = 0,
    max_nodes: int = 0,
    max_edges: int = 0,
    disabled_types: Collection[str] = (),
    outbound: OutboundPolicy | None = None,
    subflows: SubflowSource | None = None,
) -> Run:
    return await _run(
        store,
        member,
        flow,
        version.graph,
        version.version,
        payload,
        new_observer,
        load_secrets,
        timeout_seconds,
        max_nodes,
        max_edges,
        disabled_types,
        outbound,
        subflows,
    )


async def _run(
    store: RunStore,
    member: Member,
    flow: Flow,
    raw_graph: dict[str, Any],
    flow_version: int | None,
    payload: dict[str, Any],
    new_observer: ObserverFactory,
    load_secrets: SecretLoader,
    timeout_seconds: float,
    max_nodes: int,
    max_edges: int,
    disabled_types: Collection[str],
    outbound: OutboundPolicy | None,
    subflows: SubflowSource | None,
) -> Run:
    graph, issues = parse_graph(raw_graph, max_nodes, max_edges, disabled_types, outbound)
    if graph is None:
        raise invalid_flow(issues)
    names = referenced_secret_names(graph)
    if subflows is not None:
        names |= await subflows.secret_names(graph)
    secrets = await load_secrets(names) if names else RunSecrets()
    observer = new_observer(flow.name)
    try:
        result = await run_flow(
            compile_graph(graph),
            payload,
            observer,
            timeout_seconds,
            secrets,
            outbound,
            subflows.access if subflows else None,
        )
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
        test=flow_version is None,
        flow_version=flow_version,
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


async def run_steps(
    store: RunStore, member: Member, run_id: uuid.UUID, read: TraceReader
) -> RunSteps:
    run = await store.get_run(member, run_id)
    if run is None:
        raise not_found("Run")
    if run.mlflow_trace_id is None:
        return RunSteps(items=[], pending=False)
    try:
        spans = await read(run.mlflow_trace_id)
    except TraceUnavailable:
        raise ApiError(
            503, "trace_unavailable", "Step history is unavailable right now. Try again shortly."
        ) from None
    if spans is None:
        age = datetime.now(UTC).replace(tzinfo=None) - run.started_at
        return RunSteps(items=[], pending=age < TRACE_GRACE)
    return RunSteps(items=build_steps(spans), pending=False)
