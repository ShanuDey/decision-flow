"""HTTP only. Run creation lives under /flows/{id}/runs but is owned by this package."""

import logging
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
from app.runs.store import FlowInfo, RunStore, get_run_store
from app.settings import get_settings
from app.tracing import MlflowObserver
from app.workspaces.deps import CurrentMember
from app.workspaces.schemas import Member

router = APIRouter(tags=["runs"])
logger = logging.getLogger(__name__)

NOT_FOUND = {404: {"model": ErrorResponse}}
INVALID = {422: {"model": ErrorResponse}}
TOO_MANY = {429: {"model": ErrorResponse}}


def get_observer_factory() -> ObserverFactory:
    return lambda name: MlflowObserver(get_settings(), name)


def get_trace_reader() -> TraceReader:
    return lambda trace_id: tracing.read_spans(get_settings(), trace_id)


async def _flow_infos(runs: RunStore, member: Member, rows: list[Run]) -> dict[uuid.UUID, FlowInfo]:
    return await runs.flow_infos(member, {r.flow_id for r in rows})


def _summary_fields(run: Run, infos: dict[uuid.UUID, FlowInfo]) -> dict[str, Any]:
    info = infos.get(run.flow_id)
    if info is None:
        logger.warning("run %s has no flow row for %s", run.id, run.flow_id)
        info = FlowInfo(name=str(run.flow_id)[:8], deleted=True)
    return {
        "run_id": run.id,
        "flow_id": run.flow_id,
        "flow_name": info.name,
        "flow_deleted": info.deleted,
        "status": run.status,
        "test": run.test,
        "flow_version": run.flow_version,
        "error": run.error,
        "duration_ms": run.duration_ms,
        "started_at": run.started_at,
    }


def _summary(run: Run, infos: dict[uuid.UUID, FlowInfo]) -> RunSummary:
    return RunSummary.model_validate(_summary_fields(run, infos))


def _run_response(run: Run) -> RunResponse:
    return RunResponse.model_validate(
        {
            "run_id": run.id,
            "status": run.status,
            "flow_version": run.flow_version,
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
    """Runs a flow inline: the latest published version, or the current draft with `test: true`.

    422 `not_published` if there is no published version. A failure or timeout is a 200 with status
    `failed`; bad input is 422; too many runs, 429.
    """
    flow = await flows_service.require_flow(flows, member, flow_id)
    version = None
    if not body.test:
        if flow.published_version is None:
            raise ApiError(
                422,
                "not_published",
                "Flow has no published version; publish it or run with test=true",
            )
        version = await flows_service.get_version(flows, member, flow_id, flow.published_version)
    async with slots.hold(member.workspace_id):
        common = {
            "timeout_seconds": limits.run_timeout_seconds,
            "max_nodes": limits.max_nodes,
            "max_edges": limits.max_edges,
        }
        if version is None:
            run = await service.run_draft(runs, member, flow, body.input, new_observer, **common)
        else:
            run = await service.run_published(
                runs, member, flow, version, body.input, new_observer, **common
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
    infos = await _flow_infos(runs, member, page)
    items = [_summary(r, infos) for r in page]
    return RunList(items=items, next_cursor=next_cursor)


@router.get("/runs/{run_id}", responses=NOT_FOUND)
async def get_run(
    run_id: uuid.UUID, member: CurrentMember, runs: Annotated[RunStore, Depends(get_run_store)]
) -> RunDetail:
    """Returns one run with its input, output and error.

    `get_run_steps` has the step-by-step trace.
    """
    run = await runs.get_run(member, run_id)
    if run is None:
        raise flows_service.not_found("Run")
    infos = await _flow_infos(runs, member, [run])
    return RunDetail.model_validate(
        {**_summary_fields(run, infos), "input": run.input, "output": run.output}
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
