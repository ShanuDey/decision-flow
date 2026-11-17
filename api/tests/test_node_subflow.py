import copy
import uuid
from typing import Any

import httpx
import pytest

from app.engine.compiler import compile_graph
from app.engine.contracts import contract_of
from app.engine.graph import Graph
from app.engine.observer import NodeInfo
from app.engine.runtime import run_flow
from app.engine.subflow import SubflowAccess
from app.engine.validate import parse_graph
from app.flows.subflows import SubflowSource
from app.limits import Limits
from app.workspaces.schemas import Member
from tests.conftest import FakeFlowStore, create_flow

CHILD_ID = str(uuid.uuid4())


def child_draft(value: str = "{{ input.amount }}", out_type: str = "number") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "variables": [],
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "data": {"inputs": [{"name": "amount", "type": "number", "required": True}]},
            },
            {
                "id": "end",
                "type": "end",
                "data": {"outputs": [{"name": "total", "type": out_type, "value": value}]},
            },
        ],
        "edges": [{"id": "e1", "source": "start", "target": "end"}],
    }


def parent_draft(
    flow_id: str = CHILD_ID, inputs: dict[str, str] | None = None, end_value: str | None = None
) -> dict[str, Any]:
    mapping = {"amount": "{{ input.amount }}"} if inputs is None else inputs
    return {
        "schema_version": 1,
        "variables": [],
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "data": {"inputs": [{"name": "amount", "type": "number", "required": True}]},
            },
            {
                "id": "sub",
                "type": "subflow",
                "data": {"flow_id": flow_id, "inputs": mapping},
            },
            {
                "id": "end",
                "type": "end",
                "data": {
                    "outputs": [
                        {
                            "name": "result",
                            "type": "number",
                            "value": end_value or "{{ nodes.sub.output.total }}",
                        }
                    ]
                },
            },
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "sub"},
            {"id": "e2", "source": "sub", "target": "end"},
        ],
    }


def graph_of(raw: dict[str, Any]) -> Graph:
    graph, issues = parse_graph(raw)
    assert graph is not None, issues
    return graph


def access(graphs: dict[str, dict[str, Any]], max_depth: int = 5) -> SubflowAccess:
    async def load(flow_id: str) -> Graph:
        if flow_id not in graphs:
            raise ValueError("the flow is missing, or has no published version")
        return graph_of(graphs[flow_id])

    return SubflowAccess(load=load, max_depth=max_depth)


class KeyRecorder:
    def __init__(self) -> None:
        self.started: list[str] = []
        self.finished: list[str] = []
        self.run_events = 0

    async def run_started(self, inputs: Any) -> None:
        self.run_events += 1

    async def node_started(self, node: NodeInfo, inputs: Any) -> None:
        self.started.append(node.key)

    async def node_finished(self, node: NodeInfo, *args: Any, **kwargs: Any) -> None:
        self.finished.append(node.key)

    async def run_finished(self, *args: Any, **kwargs: Any) -> None:
        self.run_events += 1


async def run(raw: dict[str, Any], payload: dict[str, Any], graphs: dict, **kw: Any):
    return await run_flow(compile_graph(graph_of(raw)), payload, subflows=access(graphs, **kw))


@pytest.mark.anyio
async def test_a_subflow_runs_the_flow_and_exposes_its_outputs() -> None:
    result = await run(parent_draft(), {"amount": 7}, {CHILD_ID: child_draft()})
    assert result.status == "succeeded" and result.output == {"result": 7}


@pytest.mark.anyio
async def test_a_failing_flow_fails_the_node_with_its_reason() -> None:
    bad = child_draft(value="oops", out_type="number")
    result = await run(parent_draft(), {"amount": 7}, {CHILD_ID: bad})
    assert result.status == "failed"
    assert result.error is not None and result.error.node_id == "sub"
    assert "the flow failed at 'end'" in result.error.message


@pytest.mark.anyio
async def test_an_unavailable_flow_fails_the_node() -> None:
    result = await run(parent_draft(), {"amount": 7}, {})
    assert result.error is not None and result.error.node_id == "sub"
    assert "no published version" in result.error.message


@pytest.mark.anyio
async def test_a_flow_that_calls_itself_stops_at_the_depth_limit() -> None:
    again = parent_draft(flow_id=CHILD_ID)
    result = await run(again, {"amount": 1}, {CHILD_ID: again}, max_depth=3)
    assert result.status == "failed"
    assert result.error is not None and "nested more than 3 levels" in result.error.message


@pytest.mark.anyio
async def test_the_flows_nodes_are_reported_under_the_subflow_node() -> None:
    recorder = KeyRecorder()
    await run_flow(
        compile_graph(graph_of(parent_draft())),
        {"amount": 7},
        recorder,
        subflows=access({CHILD_ID: child_draft()}),
    )
    assert recorder.started == ["start", "sub", "sub>start", "sub>end", "end"]
    assert recorder.finished == ["start", "sub>start", "sub>end", "sub", "end"]
    assert recorder.run_events == 2


@pytest.mark.anyio
async def test_without_access_a_subflow_node_fails() -> None:
    result = await run_flow(compile_graph(graph_of(parent_draft())), {"amount": 1})
    assert result.error is not None and "not available" in result.error.message


def contracts_for(draft: dict[str, Any]) -> dict:
    return {CHILD_ID: contract_of(graph_of(draft))}


def codes(raw: dict[str, Any], contracts: dict | None) -> list[str]:
    return [i.code for i in parse_graph(raw, contracts=contracts)[1]]


def test_a_flow_must_be_picked() -> None:
    assert codes(parent_draft(flow_id=""), None) == ["subflow_not_selected"]


def test_contract_checks_are_skipped_without_contracts() -> None:
    assert codes(parent_draft(inputs={"nope": "1"}), None) == []


def test_an_unavailable_flow_is_reported() -> None:
    assert codes(parent_draft(), {}) == ["subflow_unavailable"]


def test_mapping_an_input_the_flow_lacks_is_reported() -> None:
    raw = parent_draft(inputs={"amount": "{{ input.amount }}", "extra": "1"})
    assert codes(raw, contracts_for(child_draft())) == ["unknown_subflow_input"]


def test_a_required_input_without_a_value_is_reported() -> None:
    assert codes(parent_draft(inputs={}), contracts_for(child_draft())) == ["missing_subflow_input"]


def test_a_later_node_may_only_read_outputs_the_flow_has() -> None:
    raw = parent_draft(end_value="{{ nodes.sub.output.nothing }}")
    assert codes(raw, contracts_for(child_draft())) == ["unknown_reference"]


def test_mapped_templates_are_checked_like_any_other() -> None:
    raw = parent_draft(inputs={"amount": "{{ input.missing }}"})
    assert codes(raw, contracts_for(child_draft())) == ["unknown_reference"]


def test_the_contract_lists_inputs_outputs_and_calls() -> None:
    contract = contract_of(graph_of(parent_draft()))
    assert [f.name for f in contract.inputs] == ["amount"]
    assert [o.name for o in contract.outputs] == ["result"]
    assert contract.calls == [CHILD_ID]


async def publish(client: httpx.AsyncClient, flow_id: str) -> None:
    response = await client.post(f"/flows/{flow_id}/publish")
    assert response.status_code == 201, response.text


async def save(client: httpx.AsyncClient, flow_id: str, draft: dict[str, Any]) -> None:
    version = (await client.get(f"/flows/{flow_id}")).json()["draft_version"]
    saved = await client.put(
        f"/flows/{flow_id}/draft", json=draft, headers={"If-Match": str(version)}
    )
    assert saved.status_code == 200


@pytest.mark.anyio
async def test_a_published_parent_runs_the_published_child(client: httpx.AsyncClient) -> None:
    child = await create_flow(client, child_draft())
    await publish(client, child["id"])
    parent = await create_flow(client, parent_draft(child["id"]))
    await publish(client, parent["id"])
    response = await client.post(f"/flows/{parent['id']}/runs", json={"input": {"amount": 9}})
    assert response.status_code == 200
    assert response.json()["output"] == {"result": 9}


@pytest.mark.anyio
async def test_a_draft_run_uses_the_childs_published_version_not_its_draft(
    client: httpx.AsyncClient,
) -> None:
    child = await create_flow(client, child_draft())
    await publish(client, child["id"])
    await save(client, child["id"], child_draft(value="{{ input.amount }} + 1"))
    parent = await create_flow(client, parent_draft(child["id"]))
    response = await client.post(
        f"/flows/{parent['id']}/runs", json={"test": True, "input": {"amount": 9}}
    )
    assert response.json()["output"] == {"result": 9}


@pytest.mark.anyio
async def test_publishing_needs_the_child_to_be_published(client: httpx.AsyncClient) -> None:
    child = await create_flow(client, child_draft())
    parent = await create_flow(client, parent_draft(child["id"]))
    response = await client.post(f"/flows/{parent['id']}/publish")
    assert response.status_code == 422
    errors = response.json()["details"]["errors"]
    assert [(e["code"], e["node_id"]) for e in errors] == [("subflow_unavailable", "sub")]


@pytest.mark.anyio
async def test_validating_names_the_input_that_no_longer_exists(
    client: httpx.AsyncClient,
) -> None:
    child = await create_flow(client, child_draft())
    await publish(client, child["id"])
    parent = await create_flow(client, parent_draft(child["id"]))
    renamed = copy.deepcopy(child_draft())
    renamed["nodes"][0]["data"]["inputs"][0]["name"] = "value"
    renamed["nodes"][1]["data"]["outputs"][0]["value"] = "{{ input.value }}"
    await save(client, child["id"], renamed)
    await publish(client, child["id"])
    response = await client.post(f"/flows/{parent['id']}/validate")
    found = {e["code"] for e in response.json()["details"]["errors"]}
    assert found == {"unknown_subflow_input", "missing_subflow_input"}


@pytest.mark.anyio
async def test_a_flow_cannot_call_itself_through_another(client: httpx.AsyncClient) -> None:
    first = await create_flow(client, child_draft())
    await publish(client, first["id"])
    second = await create_flow(client, parent_draft(first["id"]))
    await publish(client, second["id"])
    await save(client, first["id"], parent_draft(second["id"], end_value="{{ input.amount }}"))
    response = await client.post(f"/flows/{first['id']}/publish")
    assert response.status_code == 422
    errors = response.json()["details"]["errors"]
    assert [(e["code"], e["node_id"]) for e in errors] == [("subflow_loop", "sub")]


@pytest.mark.anyio
async def test_a_flow_from_another_workspace_cannot_be_called(
    flow_store: FakeFlowStore,
) -> None:
    owner = Member(user_id=uuid.uuid4(), workspace_id=uuid.uuid4())
    stranger = Member(user_id=uuid.uuid4(), workspace_id=uuid.uuid4())
    child = await flow_store.create_flow(owner, "Child", child_draft())
    await flow_store.publish(owner, child.id, child.draft_version, soft=False)
    limits = Limits(_env_file=None)
    assert await SubflowSource(flow_store, owner, limits).load(str(child.id))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="no published version"):
        await SubflowSource(flow_store, stranger, limits).load(str(child.id))  # type: ignore[arg-type]
