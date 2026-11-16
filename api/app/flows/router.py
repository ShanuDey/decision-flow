"""HTTP only: parsing, status codes, response shapes. Logic lives in service.py."""

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query, status

from app.errors import ApiError, ErrorResponse
from app.flows import service
from app.flows.format import flow_format
from app.flows.schemas import (
    DraftSaved,
    EvaluateRequest,
    EvaluateResponse,
    FlowCreate,
    FlowDetail,
    FlowFormat,
    FlowList,
    FlowRename,
    FlowSummary,
    ValidateResponse,
    VersionDetail,
    VersionList,
    VersionSummary,
)
from app.flows.store import FlowStore, get_store
from app.limits import Limits, get_limits
from app.security.policy import outbound_policy
from app.settings import Settings, get_settings
from app.workspaces.deps import CurrentMember

router = APIRouter(tags=["flows"])
# Stateless, so mounted without the per-user write limit (see main.py).
expressions_router = APIRouter(tags=["flows"])
Store = Annotated[FlowStore, Depends(get_store)]
Lim = Annotated[Limits, Depends(get_limits)]
AppSettings = Annotated[Settings, Depends(get_settings)]

NOT_FOUND = {404: {"model": ErrorResponse}}
CONFLICT = {409: {"model": ErrorResponse}}
INVALID = {422: {"model": ErrorResponse}}
Sort = Literal["name", "-name", "created_at", "-created_at", "updated_at", "-updated_at"]


@router.get("/flow-format")
async def get_flow_format() -> FlowFormat:
    """Explains how a flow graph is written: a guide, the JSON Schema and worked examples.

    Read it before saving a draft.
    """
    return flow_format()


@router.post("/flows", status_code=status.HTTP_201_CREATED, responses=CONFLICT)
async def create_flow(
    body: FlowCreate, store: Store, member: CurrentMember, limits: Lim
) -> FlowDetail:
    """Creates a flow. Without `draft` it starts as a blank Start to End graph.

    It has no published version yet.
    """
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
    """Lists your flows, most recently edited first.

    `q` filters by name; `published_version` is null until a flow is published.
    """
    flows, total = await store.list_flows(member, q, sort, page, page_size)
    return FlowList(
        items=[FlowSummary.model_validate(f, from_attributes=True) for f in flows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/flows/{flow_id}", responses=NOT_FOUND)
async def get_flow(flow_id: uuid.UUID, store: Store, member: CurrentMember) -> FlowDetail:
    """Returns a flow with its current draft graph and `draft_version`.

    Saving the draft needs that `draft_version` as `If-Match`.
    """
    flow = await service.require_flow(store, member, flow_id)
    return FlowDetail.model_validate(flow, from_attributes=True)


@router.patch("/flows/{flow_id}", responses=NOT_FOUND)
async def rename_flow(
    flow_id: uuid.UUID, body: FlowRename, store: Store, member: CurrentMember
) -> FlowSummary:
    """Renames a flow. Its draft and history are not affected."""
    flow = await service.rename_flow(store, member, flow_id, body.name)
    return FlowSummary.model_validate(flow, from_attributes=True)


@router.delete("/flows/{flow_id}", status_code=status.HTTP_204_NO_CONTENT, responses=NOT_FOUND)
async def delete_flow(
    flow_id: uuid.UUID, store: Store, member: CurrentMember, settings: AppSettings
) -> None:
    """Hard mode removes the flow and its runs for good; soft mode only hides the flow."""
    await service.delete_flow(store, member, flow_id, soft=settings.delete_mode == "soft")


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
    if_match: Annotated[
        str | None,
        Header(description="Required: the `draft_version` you last read (from the flow)."),
    ] = None,
) -> DraftSaved:
    """Replaces the whole draft graph.

    Send the `draft_version` you last read as `If-Match`; a stale value is 409 `draft_conflict`.
    Saves even an invalid graph (autosave); problems are reported by `validate_flow`.
    """
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
    flow_id: uuid.UUID, store: Store, member: CurrentMember, limits: Lim, settings: AppSettings
) -> ValidateResponse:
    """Checks the saved draft without publishing it.

    Returns `valid: true`, or 422 `invalid_flow` listing each problem with its `node_id`
    and `field`.
    """
    flow = await service.require_flow(store, member, flow_id)
    service.validate_draft(flow, limits, outbound_policy(settings, limits))
    return ValidateResponse(valid=True)


@router.post(
    "/flows/{flow_id}/publish",
    status_code=status.HTTP_201_CREATED,
    responses={**NOT_FOUND, **CONFLICT, **INVALID},
)
async def publish_flow(
    flow_id: uuid.UUID, store: Store, member: CurrentMember, limits: Lim, settings: AppSettings
) -> VersionDetail:
    """Validates the draft, then freezes it as the next numbered version.

    409 `nothing_to_publish` if the draft has not changed since the last version.
    """
    version = await service.publish_flow(
        store,
        member,
        flow_id,
        limits,
        soft=settings.delete_mode == "soft",
        outbound=outbound_policy(settings, limits),
    )
    return VersionDetail.model_validate(version, from_attributes=True)


@router.get("/flows/{flow_id}/versions", responses=NOT_FOUND)
async def list_versions(
    flow_id: uuid.UUID, store: Store, member: CurrentMember, limits: Lim
) -> VersionList:
    """Lists a flow's published versions, newest first.

    `keep_latest` is how many are retained.
    """
    versions = await service.list_versions(store, member, flow_id)
    return VersionList(
        items=[VersionSummary.model_validate(v, from_attributes=True) for v in versions],
        keep_latest=limits.max_versions_per_flow,
    )


@router.get("/flows/{flow_id}/versions/{version}", responses=NOT_FOUND)
async def get_version(
    flow_id: uuid.UUID, version: int, store: Store, member: CurrentMember
) -> VersionDetail:
    """Returns one published version with its frozen graph."""
    found = await service.get_version(store, member, flow_id, version)
    return VersionDetail.model_validate(found, from_attributes=True)


@expressions_router.post("/expressions/evaluate")
async def evaluate_expression(body: EvaluateRequest) -> EvaluateResponse:
    """Stateless helper for the editor's Test pane and validity strip."""
    return service.evaluate_source(body)
