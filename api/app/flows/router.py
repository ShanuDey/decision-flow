"""HTTP only: parsing, status codes, response shapes. Logic lives in service.py."""

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query, status

from app.errors import ApiError, ErrorResponse
from app.flows import service
from app.flows.models import Run
from app.flows.schemas import (
    DraftSaved,
    FlowCreate,
    FlowDetail,
    FlowList,
    FlowSummary,
    RunRequest,
    RunResponse,
    ValidateResponse,
)
from app.flows.store import FlowStore, get_store

router = APIRouter(tags=["flows"])
Store = Annotated[FlowStore, Depends(get_store)]

NOT_FOUND = {404: {"model": ErrorResponse}}
INVALID = {422: {"model": ErrorResponse}}
Sort = Literal["name", "-name", "created_at", "-created_at", "updated_at", "-updated_at"]


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


@router.post("/flows", status_code=status.HTTP_201_CREATED)
async def create_flow(body: FlowCreate, store: Store) -> FlowDetail:
    flow = await store.create_flow(body.name, body.draft or service.blank_draft())
    return FlowDetail.model_validate(flow, from_attributes=True)


@router.get("/flows")
async def list_flows(
    store: Store,
    q: str | None = None,
    sort: Sort = "-updated_at",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> FlowList:
    flows, total = await store.list_flows(q, sort, page, page_size)
    return FlowList(
        items=[FlowSummary.model_validate(f, from_attributes=True) for f in flows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/flows/{flow_id}", responses=NOT_FOUND)
async def get_flow(flow_id: uuid.UUID, store: Store) -> FlowDetail:
    flow = await service.require_flow(store, flow_id)
    return FlowDetail.model_validate(flow, from_attributes=True)


@router.put(
    "/flows/{flow_id}/draft",
    responses={**NOT_FOUND, 409: {"model": ErrorResponse}, 428: {"model": ErrorResponse}},
)
async def save_draft(
    flow_id: uuid.UUID,
    draft: dict[str, Any],
    store: Store,
    if_match: Annotated[str | None, Header()] = None,
) -> DraftSaved:
    """Saves even an invalid graph (autosave); problems are reported by `validate_flow`."""
    if if_match is None:
        raise ApiError(428, "precondition_required", "If-Match: <draft_version> is required")
    try:
        expected = int(if_match.strip('"'))
    except ValueError:
        raise ApiError(428, "precondition_required", "If-Match must be a draft version") from None
    saved = await service.save_draft(store, flow_id, draft, expected)
    return DraftSaved(draft_version=saved.draft_version)


@router.post("/flows/{flow_id}/validate", responses={**NOT_FOUND, **INVALID})
async def validate_flow(flow_id: uuid.UUID, store: Store) -> ValidateResponse:
    service.validate_draft(await service.require_flow(store, flow_id))
    return ValidateResponse(valid=True)


@router.post("/flows/{flow_id}/runs", responses={**NOT_FOUND, **INVALID})
async def create_run(flow_id: uuid.UUID, body: RunRequest, store: Store) -> RunResponse:
    """Runs inline. A failure inside the flow is a 200 with status "failed"; bad input is a 422."""
    flow = await service.require_flow(store, flow_id)
    if not body.test:
        raise ApiError(422, "not_published", "Flow has no published version; run with test=true")
    return _run_response(await service.run_draft(store, flow, body.input))


@router.get("/runs/{run_id}", responses=NOT_FOUND)
async def get_run(run_id: uuid.UUID, store: Store) -> RunResponse:
    run = await store.get_run(run_id)
    if run is None:
        raise service.not_found("Run")
    return _run_response(run)
