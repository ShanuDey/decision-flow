"""HTTP only. Run creation lives under /flows/{id}/runs but is owned by this package."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query

from app import tracing
from app.errors import ApiError, ErrorResponse
from app.flows import service as flows_service
from app.flows.store import FlowStore, get_store
from app.limits import Limits, get_limits
from app.ratelimit import limit_runs
from app.runs import service
from app.runs.models import Run
from app.runs.schemas import RunDetail, RunList, RunRequest, RunResponse, RunSteps, RunSummary
from app.runs.service import ObserverFactory, TraceReader
from app.runs.slots import RunSlots, get_run_slots
from app.runs.store import RunStore, get_run_store
from app.settings import get_settings
from app.tracing import MlflowObserver
from app.workspaces.deps import CurrentMember

router = APIRouter(tags=["runs"])

NOT_FOUND = {404: {"model": ErrorResponse}}
INVALID = {422: {"model": ErrorResponse}}
TOO_MANY = {429: {"model": ErrorResponse}}


def get_observer_factory() -> ObserverFactory:
    return lambda name: MlflowObserver(get_settings(), name)


def get_trace_reader() -> TraceReader:
    return lambda trace_id: tracing.read_spans(get_settings(), trace_id)


def _summary_fields(run: Run) -> dict[str, Any]:
    return {
        "run_id": run.id,
        "flow_id": run.flow_id,
        "status": run.status,
        "test": run.test,
        "error": run.error,
        "duration_ms": run.duration_ms,
        "started_at": run.started_at,
    }


def _summary(run: Run) -> RunSummary:
    return RunSummary.model_validate(_summary_fields(run))


def _run_response(run: Run) -> RunResponse:
    return RunResponse.model_validate(
        {
            "run_id": run.id,
            "status": run.status,
            "output": run.output,
            "error": run.error,
            "duration_ms": run.duration_ms,
        }
    )


@router.post(
    "/flows/{flow_id}/runs",
    responses={**NOT_FOUND, **INVALID, **TOO_MANY},
    dependencies=[Depends(limit_runs)],
)
async def create_run(
    flow_id: uuid.UUID,
    body: RunRequest,
    member: CurrentMember,
    flows: Annotated[FlowStore, Depends(get_store)],
    runs: Annotated[RunStore, Depends(get_run_store)],
    new_observer: Annotated[ObserverFactory, Depends(get_observer_factory)],
    slots: Annotated[RunSlots, Depends(get_run_slots)],
    limits: Annotated[Limits, Depends(get_limits)],
) -> RunResponse:
    """Runs inline. A failure or timeout is a 200 "failed"; bad input is 422; too many runs, 429."""
    flow = await flows_service.require_flow(flows, member, flow_id)
    if not body.test:
        raise ApiError(422, "not_published", "Flow has no published version; run with test=true")
    async with slots.hold(member.workspace_id):
        run = await service.run_draft(
            runs,
            member,
            flow,
            body.input,
            new_observer,
            timeout_seconds=limits.run_timeout_seconds,
            max_nodes=limits.max_nodes,
            max_edges=limits.max_edges,
        )
    return _run_response(run)


@router.get("/runs", responses=INVALID)
async def list_runs(
    runs: Annotated[RunStore, Depends(get_run_store)],
    member: CurrentMember,
    flow_id: uuid.UUID | None = None,
    status: Literal["succeeded", "failed"] | None = None,
    test: bool | None = None,
    started_from: Annotated[datetime | None, Query(alias="from")] = None,
    started_to: Annotated[datetime | None, Query(alias="to")] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> RunList:
    """Newest first; pass `next_cursor` back as `cursor` for the next page."""
    page, next_cursor = await service.list_runs(
        runs,
        member,
        flow_id=flow_id,
        status=status,
        test=test,
        started_from=started_from,
        started_to=started_to,
        cursor=cursor,
        limit=limit,
    )
    items = [_summary(r) for r in page]
    return RunList(items=items, next_cursor=next_cursor)


@router.get("/runs/{run_id}", responses=NOT_FOUND)
async def get_run(
    run_id: uuid.UUID, member: CurrentMember, runs: Annotated[RunStore, Depends(get_run_store)]
) -> RunDetail:
    run = await runs.get_run(member, run_id)
    if run is None:
        raise flows_service.not_found("Run")
    return RunDetail.model_validate(
        {**_summary_fields(run), "input": run.input, "output": run.output}
    )


@router.get("/runs/{run_id}/steps", responses={**NOT_FOUND, 503: {"model": ErrorResponse}})
async def get_run_steps(
    run_id: uuid.UUID,
    member: CurrentMember,
    runs: Annotated[RunStore, Depends(get_run_store)],
    read: Annotated[TraceReader, Depends(get_trace_reader)],
) -> RunSteps:
    """Step history from the trace store; `pending` while the trace is still being written."""
    return await service.run_steps(runs, member, run_id, read)
