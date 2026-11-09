"""Flow use cases. No HTTP types except ApiError."""

import uuid
from typing import Any

from app.engine.compiler import compile_graph
from app.engine.inputs import InputValidationError
from app.engine.issues import Issue
from app.engine.runtime import run_flow
from app.engine.validate import parse_graph
from app.errors import ApiError
from app.flows.models import Flow, Run
from app.flows.store import FlowStore


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


async def require_flow(store: FlowStore, flow_id: uuid.UUID) -> Flow:
    flow = await store.get_flow(flow_id)
    if flow is None:
        raise not_found("Flow")
    return flow


def validate_draft(flow: Flow) -> None:
    _, issues = parse_graph(flow.draft)
    if issues:
        raise invalid_flow(issues)


async def save_draft(
    store: FlowStore, flow_id: uuid.UUID, draft: dict[str, Any], expected_version: int
) -> Flow:
    saved = await store.save_draft(flow_id, draft, expected_version)
    if saved is not None:
        return saved
    current = await require_flow(store, flow_id)
    raise ApiError(
        409,
        "draft_conflict",
        "The draft changed since you loaded it",
        {"draft_version": current.draft_version},
    )


async def run_draft(store: FlowStore, flow: Flow, payload: dict[str, Any]) -> Run:
    graph, issues = parse_graph(flow.draft)
    if graph is None:
        raise invalid_flow(issues)
    try:
        result = await run_flow(compile_graph(graph), payload)
    except InputValidationError as exc:
        first = exc.issues[0]
        raise ApiError(
            422,
            "invalid_input",
            str(exc),
            {"field": first.field, "errors": [i.model_dump() for i in exc.issues]},
        ) from exc
    return await store.add_run(
        Run(
            flow_id=flow.id,
            status=result.status,
            test=True,
            input=payload,
            output=result.output,
            error=result.error.model_dump() if result.error else None,
            duration_ms=result.duration_ms,
        )
    )
