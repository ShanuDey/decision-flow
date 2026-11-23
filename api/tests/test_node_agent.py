import uuid
from typing import Any

import pytest

from app.connections.catalog import BY_ID
from app.connections.types import resolve
from app.engine.compiler import compile_graph
from app.engine.contracts import contract_of
from app.engine.run_secrets import RunSecrets
from app.engine.runtime import run_flow
from app.engine.validate import parse_graph
from app.flows.subflows import called_flows, loop_issues
from tests.chat_server import chat_server
from tests.test_agent_core import asks, says
from tests.test_node_http_request import anyio_backend, policy  # noqa: F401
from tests.test_node_subflow import CHILD_ID, KeyRecorder, access, child_draft, graph_of

pytestmark = pytest.mark.anyio

CONNECTION_ID = "5f0a2c1e-7b3d-4e6a-9c8f-1d2e3f4a5b6c"
TOOL = {"flow_id": CHILD_ID, "name": "double", "description": "Returns the amount"}


def flow(**data: Any) -> dict[str, Any]:
    node = {
        "connection_id": CONNECTION_ID,
        "prompt": "Handle {{ input.who }}",
        "tools": [TOOL],
    } | data
    return {
        "schema_version": 1,
        "variables": [],
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "data": {"inputs": [{"name": "who", "type": "string", "required": False}]},
            },
            {"id": "bot", "type": "agent", "data": node},
            {
                "id": "end",
                "type": "end",
                "data": {
                    "outputs": [
                        {"name": "answer", "type": "string", "value": "{{ nodes.bot.output.text }}"}
                    ]
                },
            },
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "bot"},
            {"id": "e2", "source": "bot", "target": "end"},
        ],
    }


def secrets(port: int) -> RunSecrets:
    values = {
        "api_key": "test-key-for-the-agent-node",
        "base_url": f"http://127.0.0.1:{port}/v1",
        "default_model": "m",
    }
    conn = resolve(BY_ID["openai_compatible"], CONNECTION_ID, "Local model", values)
    return RunSecrets(connections={CONNECTION_ID: conn})


async def run(
    raw: dict[str, Any], port: int, observer: Any = None, children: Any = None, **kw: Any
):
    parsed, issues = parse_graph(raw)
    assert parsed is not None, issues
    graphs = {CHILD_ID: child_draft()} if children is None else children
    return await run_flow(
        compile_graph(parsed),
        {"who": "Ada"},
        observer,
        secrets=secrets(port),
        outbound=policy(),
        subflows=access(graphs, **kw),
    )


async def test_the_model_runs_a_flow_as_a_tool_and_answers() -> None:
    script = [asks(("double", '{"amount": 21}')), says("The total is 21")]
    async with chat_server(script=script) as (port, seen):
        result = await run(flow(instructions="Be brief"), port)

    assert result.status == "succeeded", result.error
    assert result.output == {"answer": "The total is 21"}
    tool = seen[0].body["tools"][0]["function"]
    assert tool["name"] == "double" and tool["description"] == "Returns the amount"
    assert tool["parameters"]["required"] == ["amount"]
    assert tool["parameters"]["properties"]["amount"] == {"type": "number"}
    assert seen[0].body["messages"][0] == {"role": "system", "content": "Be brief"}
    assert seen[0].body["messages"][1]["content"] == "Handle Ada"
    assert seen[1].body["messages"][-1]["content"] == '{"total": 21}'


async def test_the_output_has_the_steps_and_the_usage() -> None:
    script = [asks(("double", '{"amount": 2}')), says("done")]
    raw = flow()
    raw["nodes"][2]["data"]["outputs"] = [
        {"name": "n", "type": "number", "value": "{{ nodes.bot.output.iterations }}"}
    ]
    async with chat_server(script=script) as (port, _):
        result = await run(raw, port)

    assert result.output == {"n": 2}


async def test_a_flows_nodes_are_reported_under_the_agent_node() -> None:
    recorder = KeyRecorder()
    script = [asks(("double", '{"amount": 2}')), says("done")]
    async with chat_server(script=script) as (port, _):
        await run(flow(), port, recorder)

    assert "bot>start" in recorder.started and "bot>end" in recorder.finished


async def test_a_tool_that_fails_is_told_to_the_model_not_the_run() -> None:
    script = [asks(("double", '{"amount": "many"}')), says("could not")]
    async with chat_server(script=script) as (port, seen):
        result = await run(flow(), port)

    assert result.status == "succeeded" and result.output == {"answer": "could not"}
    assert seen[1].body["messages"][-1]["content"].startswith("error: the flow rejected its input")


async def test_a_flow_that_fails_inside_is_told_to_the_model() -> None:
    bad = child_draft(value="oops", out_type="number")
    script = [asks(("double", '{"amount": 1}')), says("sorry")]
    async with chat_server(script=script) as (port, seen):
        result = await run(flow(), port, children={CHILD_ID: bad})

    assert result.status == "succeeded"
    assert "the flow failed at 'end'" in seen[1].body["messages"][-1]["content"]


async def test_hitting_the_iteration_limit_fails_the_node() -> None:
    async with chat_server(script=[asks(("double", '{"amount": 1}'))]) as (port, _):
        result = await run(flow(max_iterations=2), port)

    assert result.status == "failed" and result.error is not None
    assert result.error.node_id == "bot" and "raise max iterations" in result.error.message


async def test_a_flow_that_is_missing_fails_the_node() -> None:
    async with chat_server() as (port, seen):
        result = await run(flow(), port, children={})

    assert result.error is not None and "no published version" in result.error.message
    assert seen == []


async def test_without_flow_access_a_node_with_tools_fails_but_one_without_runs() -> None:
    parsed, _ = parse_graph(flow())
    assert parsed is not None
    async with chat_server("plain answer") as (port, _):
        no_access = await run_flow(
            compile_graph(parsed), {"who": "Ada"}, secrets=secrets(port), outbound=policy()
        )
        bare = parse_graph(flow(tools=[]))[0]
        assert bare is not None
        plain = await run_flow(
            compile_graph(bare), {"who": "Ada"}, secrets=secrets(port), outbound=policy()
        )

    assert no_access.error is not None and "not available" in no_access.error.message
    assert plain.output == {"answer": "plain answer"}


async def test_an_agent_that_reaches_itself_stops_at_the_depth_limit() -> None:
    again = flow(max_iterations=2)
    async with chat_server(script=[asks(("double", '{"who": "Bo"}'))]) as (port, seen):
        result = await run(again, port, children={CHILD_ID: again}, max_depth=2)

    assert result.status == "failed"
    assert any("nested more than 2 levels" in str(call.body) for call in seen)


def issues(raw: dict[str, Any], contracts: dict | None = None) -> list[tuple[str, str | None]]:
    return [(i.code, i.field) for i in parse_graph(raw, contracts=contracts)[1]]


def test_a_node_needs_a_connection_and_a_task() -> None:
    raw = flow(connection_id="", prompt=" ", tools=[])
    assert [c for c, _ in issues(raw)] == ["missing_connection", "missing_prompt"]


def test_each_tool_needs_a_flow_a_valid_unique_name_and_a_description() -> None:
    tools = [
        {"flow_id": "", "name": "bad name", "description": "x"},
        {"flow_id": CHILD_ID, "name": "ok", "description": ""},
        {"flow_id": CHILD_ID, "name": "ok", "description": "x"},
    ]
    assert issues(flow(tools=tools)) == [
        ("tool_not_selected", "data.tools.0.flow_id"),
        ("invalid_tool_name", "data.tools.0.name"),
        ("missing_tool_description", "data.tools.1.description"),
        ("duplicate_tool_name", "data.tools.2.name"),
    ]


def test_a_tool_whose_flow_is_unavailable_is_reported() -> None:
    assert issues(flow(), contracts={}) == [("subflow_unavailable", "data.tools.0.flow_id")]
    contracts = {CHILD_ID: contract_of(graph_of(child_draft()))}
    assert issues(flow(), contracts=contracts) == []


def test_a_later_node_may_only_read_the_agents_outputs() -> None:
    raw = flow()
    raw["nodes"][2]["data"]["outputs"][0]["value"] = "{{ nodes.bot.output.nope }}"
    assert [c for c, _ in issues(raw)] != []


def test_the_tools_flows_are_listed_for_callers_and_loop_checks() -> None:
    graph = graph_of(flow())
    assert contract_of(graph).calls == [CHILD_ID]
    assert called_flows(flow()) == [("bot", CHILD_ID, "data.tools.0.flow_id")]
    own = uuid.UUID(CHILD_ID)
    contracts = {CHILD_ID: contract_of(graph)}
    found = loop_issues(own, flow(), contracts)
    assert [(i.code, i.node_id, i.field) for i in found] == [
        ("subflow_loop", "bot", "data.tools.0.flow_id")
    ]


def test_a_draft_that_is_not_valid_json_shape_still_lists_its_calls() -> None:
    raw = {"nodes": [{"id": "a", "type": "agent", "data": {"tools": [1, {"flow_id": 3}]}}]}
    assert called_flows(raw) == []
