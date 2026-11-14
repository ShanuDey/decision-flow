"""HTTP only: parsing, status codes, response shapes. Logic lives in service.py."""

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query, status

from app.errors import ApiError, ErrorResponse
from app.flows import service
from app.flows.schemas import (
    DraftSaved,
    FlowCreate,
    FlowDetail,
    FlowList,
    FlowRename,
    FlowSummary,
    ValidateResponse,
)
from app.flows.store import FlowStore, get_store
from app.limits import Limits, get_limits
from app.workspaces.deps import CurrentMember

router = APIRouter(tags=["flows"])
Store = Annotated[FlowStore, Depends(get_store)]
Lim = Annotated[Limits, Depends(get_limits)]

NOT_FOUND = {404: {"model": ErrorResponse}}
CONFLICT = {409: {"model": ErrorResponse}}
INVALID = {422: {"model": ErrorResponse}}
Sort = Literal["name", "-name", "created_at", "-created_at", "updated_at", "-updated_at"]


@router.post("/flows", status_code=status.HTTP_201_CREATED, responses=CONFLICT)
async def create_flow(
    body: FlowCreate, store: Store, member: CurrentMember, limits: Lim
) -> FlowDetail:
    flow = await service.create_flow(store, member, body.name, body.draft, limits)
    return FlowDetail.model_validate(flow, from_attributes=True)


@router.get("/flows")
async def list_flows(
    store: Store,
    member: CurrentMember,
    q: str | None = None,
    sort: Sort = "-updated_at",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> FlowList:
    flows, total = await store.list_flows(member, q, sort, page, page_size)
    return FlowList(
        items=[FlowSummary.model_validate(f, from_attributes=True) for f in flows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/flows/{flow_id}", responses=NOT_FOUND)
async def get_flow(flow_id: uuid.UUID, store: Store, member: CurrentMember) -> FlowDetail:
    flow = await service.require_flow(store, member, flow_id)
    return FlowDetail.model_validate(flow, from_attributes=True)


@router.patch("/flows/{flow_id}", responses=NOT_FOUND)
async def rename_flow(
    flow_id: uuid.UUID, body: FlowRename, store: Store, member: CurrentMember
) -> FlowSummary:
    flow = await service.rename_flow(store, member, flow_id, body.name)
    return FlowSummary.model_validate(flow, from_attributes=True)


@router.delete("/flows/{flow_id}", status_code=status.HTTP_204_NO_CONTENT, responses=NOT_FOUND)
async def delete_flow(flow_id: uuid.UUID, store: Store, member: CurrentMember) -> None:
    """Removes the flow and its runs for good."""
    await service.delete_flow(store, member, flow_id)


@router.put(
    "/flows/{flow_id}/draft",
    responses={
        **NOT_FOUND,
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        428: {"model": ErrorResponse},
    },
)
async def save_draft(
    flow_id: uuid.UUID,
    draft: dict[str, Any],
    store: Store,
    member: CurrentMember,
    if_match: Annotated[str | None, Header()] = None,
) -> DraftSaved:
    """Saves even an invalid graph (autosave); problems are reported by `validate_flow`."""
    if if_match is None:
        raise ApiError(428, "precondition_required", "If-Match: <draft_version> is required")
    try:
        expected = int(if_match.strip('"'))
    except ValueError:
        raise ApiError(400, "invalid_if_match", "If-Match must be a draft version number") from None
    saved = await service.save_draft(store, member, flow_id, draft, expected)
    return DraftSaved(draft_version=saved.draft_version)


@router.post("/flows/{flow_id}/validate", responses={**NOT_FOUND, **INVALID})
async def validate_flow(
    flow_id: uuid.UUID, store: Store, member: CurrentMember, limits: Lim
) -> ValidateResponse:
    service.validate_draft(await service.require_flow(store, member, flow_id), limits)
    return ValidateResponse(valid=True)
