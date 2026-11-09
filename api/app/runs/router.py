"""HTTP only. Run creation lives under /flows/{id}/runs but is owned by this package."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.errors import ApiError, ErrorResponse
from app.flows import service as flows_service
from app.flows.store import FlowStore, get_store
from app.runs import service
from app.runs.models import Run
from app.runs.schemas import RunRequest, RunResponse
from app.runs.service import ObserverFactory
from app.runs.store import RunStore, get_run_store
from app.settings import get_settings
from app.tracing import MlflowObserver

router = APIRouter(tags=["runs"])

NOT_FOUND = {404: {"model": ErrorResponse}}
INVALID = {422: {"model": ErrorResponse}}


def get_observer_factory() -> ObserverFactory:
    return lambda name: MlflowObserver(get_settings(), name)


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


@router.post("/flows/{flow_id}/runs", responses={**NOT_FOUND, **INVALID})
async def create_run(
    flow_id: uuid.UUID,
    body: RunRequest,
    flows: Annotated[FlowStore, Depends(get_store)],
    runs: Annotated[RunStore, Depends(get_run_store)],
    new_observer: Annotated[ObserverFactory, Depends(get_observer_factory)],
) -> RunResponse:
    """Runs inline. A failure inside the flow is a 200 with status "failed"; bad input is a 422."""
    flow = await flows_service.require_flow(flows, flow_id)
    if not body.test:
        raise ApiError(422, "not_published", "Flow has no published version; run with test=true")
    return _run_response(await service.run_draft(runs, flow, body.input, new_observer))


@router.get("/runs/{run_id}", responses=NOT_FOUND)
async def get_run(
    run_id: uuid.UUID, runs: Annotated[RunStore, Depends(get_run_store)]
) -> RunResponse:
    run = await runs.get_run(run_id)
    if run is None:
        raise flows_service.not_found("Run")
    return _run_response(run)
