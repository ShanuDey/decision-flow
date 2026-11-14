"""Flow use cases. No HTTP types except ApiError."""

import uuid
from typing import Any

from app.engine.issues import Issue
from app.engine.validate import parse_graph
from app.errors import ApiError
from app.flows.models import Flow
from app.flows.store import FlowStore
from app.workspaces.schemas import Member


def blank_draft() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "variables": [],
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "name": "Start",
                "position": {"x": 0, "y": 0},
                "data": {"inputs": []},
            },
            {
                "id": "end",
                "type": "end",
                "name": "End",
                "position": {"x": 300, "y": 0},
                "data": {"outputs": []},
            },
        ],
        "edges": [{"id": "e1", "source": "start", "target": "end", "sourceHandle": None}],
    }


def invalid_flow(issues: list[Issue]) -> ApiError:
    first = issues[0]
    return ApiError(
        422,
        "invalid_flow",
        first.message,
        {
            "node_id": first.node_id,
            "field": first.field,
            "errors": [i.model_dump() for i in issues],
        },
    )


def not_found(what: str) -> ApiError:
    return ApiError(404, "not_found", f"{what} not found")


async def require_flow(store: FlowStore, member: Member, flow_id: uuid.UUID) -> Flow:
    flow = await store.get_flow(member, flow_id)
    if flow is None:
        raise not_found("Flow")
    return flow


def validate_draft(flow: Flow) -> None:
    _, issues = parse_graph(flow.draft)
    if issues:
        raise invalid_flow(issues)


async def rename_flow(store: FlowStore, member: Member, flow_id: uuid.UUID, name: str) -> Flow:
    flow = await store.rename_flow(member, flow_id, name)
    if flow is None:
        raise not_found("Flow")
    return flow


async def save_draft(
    store: FlowStore,
    member: Member,
    flow_id: uuid.UUID,
    draft: dict[str, Any],
    expected_version: int,
) -> Flow:
    saved = await store.save_draft(member, flow_id, draft, expected_version)
    if saved is not None:
        return saved
    current = await require_flow(store, member, flow_id)
    raise ApiError(
        409,
        "draft_conflict",
        "The draft changed since you loaded it",
        {"draft_version": current.draft_version},
    )
