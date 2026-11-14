"""Flow use cases. No HTTP types except ApiError."""

import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder

from app.engine import expressions, templates
from app.engine.issues import Issue
from app.engine.validate import parse_graph
from app.errors import ApiError
from app.flows.models import Flow
from app.flows.schemas import EvaluateRequest, EvaluateResponse
from app.flows.store import FlowStore
from app.limits import Limits
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


def validate_draft(flow: Flow, limits: Limits) -> None:
    _, issues = parse_graph(flow.draft, limits.max_nodes, limits.max_edges)
    if issues:
        raise invalid_flow(issues)


async def create_flow(
    store: FlowStore, member: Member, name: str, draft: dict[str, Any] | None, limits: Limits
) -> Flow:
    cap = limits.max_flows_per_user
    if cap and (count := await store.count_flows(member)) >= cap:
        raise ApiError(
            409,
            "flow_limit_reached",
            f"You have {count} flows; the limit is {cap}.",
            {"limit": cap, "count": count, **limits.notice_details()},
        )
    return await store.create_flow(member, name, draft or blank_draft())


async def rename_flow(store: FlowStore, member: Member, flow_id: uuid.UUID, name: str) -> Flow:
    flow = await store.rename_flow(member, flow_id, name)
    if flow is None:
        raise not_found("Flow")
    return flow


async def delete_flow(store: FlowStore, member: Member, flow_id: uuid.UUID) -> None:
    if not await store.delete_flow(member, flow_id):
        raise not_found("Flow")


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


def _json_safe(value: Any) -> Any:
    # CEL can return bytes or durations, which JSON cannot carry; show their text instead.
    try:
        return jsonable_encoder(value)
    except Exception:  # noqa: BLE001
        return str(value)


def evaluate_source(body: EvaluateRequest) -> EvaluateResponse:
    """Checks (and, with a scope, evaluates) one expression or template for the editor."""
    scope = body.scope or {}
    try:
        if body.kind == "template":
            templates.references(body.source)
            result = templates.render(body.source, scope) if body.scope is not None else None
            return EvaluateResponse(valid=True, result=_json_safe(result))
        compiled = expressions.compile(body.source)
        if body.scope is None:
            return EvaluateResponse(valid=True, return_type=compiled.return_type)
        result = expressions.evaluate(compiled, scope)
        return EvaluateResponse(
            valid=True, return_type=compiled.return_type, result=_json_safe(result)
        )
    except (expressions.ExpressionError, templates.TemplateError) as exc:
        return EvaluateResponse(valid=False, error=str(exc))
