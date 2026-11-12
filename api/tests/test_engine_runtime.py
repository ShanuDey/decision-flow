import json
from pathlib import Path

import pytest

from app.engine.compiler import compile_graph
from app.engine.inputs import InputValidationError
from app.engine.runtime import run_flow
from app.engine.validate import parse_graph
from tests.recorder import Recorder

FIXTURE = Path(__file__).resolve().parents[2] / "examples" / "flows" / "start-end.json"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def raw() -> dict:
    return json.loads(FIXTURE.read_text())


def build(raw: dict):
    graph, issues = parse_graph(raw)
    assert issues == [], issues
    return compile_graph(graph)


@pytest.mark.anyio
async def test_golden_fixture_runs_start_to_end(raw: dict) -> None:
    result = await run_flow(build(raw), {"amount": 5000})
    assert result.status == "succeeded"
    assert result.error is None
    assert result.output == {
        "amount": 5000,
        "tier": "silver",
    }


@pytest.mark.anyio
async def test_explicit_input_overrides_default(raw: dict) -> None:
    result = await run_flow(build(raw), {"amount": 1.5, "tier": "gold"})
    assert result.output == {"amount": 1.5, "tier": "gold"}


@pytest.mark.anyio
async def test_invalid_input_raises_before_running_and_names_the_field(raw: dict) -> None:
    recorder = Recorder()
    with pytest.raises(InputValidationError) as exc:
        await run_flow(build(raw), {"amount": "5000"}, recorder)
    assert [(i.field, i.message) for i in exc.value.issues] == [("amount", "expected number")]
    assert recorder.events == []


@pytest.mark.anyio
async def test_observer_sees_each_node_in_order(raw: dict) -> None:
    recorder = Recorder()
    await run_flow(build(raw), {"amount": 1}, recorder)
    assert recorder.events == [
        ("run_started",),
        ("started", "start"),
        ("finished", "start", "ok", None),
        ("started", "end"),
        ("finished", "end", "ok", None),
        ("run_finished", "succeeded", None),
    ]


@pytest.mark.anyio
async def test_failure_inside_the_flow_is_a_result_naming_the_node(raw: dict) -> None:
    raw["nodes"][0]["data"]["inputs"].append({"name": "note", "type": "string", "required": False})
    raw["nodes"][1]["data"]["outputs"].append(
        {"name": "note", "type": "string", "value": "{{ input.note }}"}
    )
    recorder = Recorder()
    result = await run_flow(build(raw), {"amount": 1}, recorder)
    assert result.status == "failed"
    assert result.output is None
    assert result.error is not None
    assert result.error.node_id == "end"
    assert "input.note is not set" in result.error.message
    assert ("finished", "end", "failed", result.error.message) in recorder.events
    assert recorder.events[-1][:2] == ("run_finished", "failed")


@pytest.mark.anyio
async def test_output_is_type_checked(raw: dict) -> None:
    raw["nodes"][1]["data"]["outputs"][0] = {
        "name": "amount",
        "type": "string",
        "value": "{{ input.amount }}",
    }
    result = await run_flow(build(raw), {"amount": 1})
    assert result.status == "failed"
    assert result.error.message == "output 'amount': expected string"


@pytest.mark.anyio
async def test_declared_variables_start_at_their_initial_value(raw: dict) -> None:
    raw["variables"] = [{"name": "approved", "type": "boolean", "initial": False}]
    raw["nodes"][1]["data"]["outputs"] = [
        {"name": "approved", "type": "boolean", "value": "{{ vars.approved }}"}
    ]
    result = await run_flow(build(raw), {"amount": 1})
    assert result.output == {"approved": False}


@pytest.mark.anyio
async def test_compiled_flow_is_reusable_across_runs(raw: dict) -> None:
    flow = build(raw)
    first = await run_flow(flow, {"amount": 1})
    second = await run_flow(flow, {"amount": 2})
    assert (first.output["amount"], second.output["amount"]) == (1, 2)


@pytest.mark.anyio
async def test_start_node_applies_defaults_when_the_graph_is_called_directly(raw: dict) -> None:
    final = await build(raw).graph.ainvoke({"input": {"amount": 1}})
    assert final["_output"] == {"amount": 1, "tier": "silver"}


@pytest.mark.anyio
async def test_start_node_rejects_bad_input_when_called_directly(raw: dict) -> None:
    from app.engine.observer import NodeError

    with pytest.raises(NodeError) as exc:
        await build(raw).graph.ainvoke({"input": {"amount": "x"}})
    assert exc.value.node_id == "start"
    assert "amount: expected number" in exc.value.message


@pytest.mark.anyio
async def test_observer_receives_what_each_node_read_and_produced(raw: dict) -> None:
    recorder = Recorder()
    await run_flow(build(raw), {"amount": 5000}, recorder)
    expected = {"amount": 5000, "tier": "silver"}
    assert recorder.run_inputs == expected
    assert recorder.run_outputs == expected
    assert recorder.node_inputs["start"]["input"] == expected  # run_flow applied defaults
    assert recorder.node_inputs["end"]["input"] == expected
    assert recorder.node_outputs == {"start": expected, "end": expected}


def test_input_schema_describes_the_start_fields_for_tools_like_studio(raw: dict) -> None:
    raw["nodes"][0]["data"]["inputs"].append(
        {"name": "my field", "type": "boolean", "required": False}
    )
    schema = build(raw).graph.get_input_jsonschema()
    inputs = schema["$defs"]["Input"]
    assert schema["required"] == ["input"]
    assert inputs["required"] == ["amount"]
    assert set(inputs["properties"]) == {"amount", "tier", "my field"}  # non-identifier names work
    assert inputs["properties"]["tier"]["enum"] == ["silver", "gold"]
    assert inputs["properties"]["tier"]["default"] == "silver"
    assert {t["type"] for t in inputs["properties"]["amount"]["anyOf"]} == {"integer", "number"}


@pytest.mark.anyio
async def test_input_schema_is_documentation_only_the_start_node_still_validates(raw: dict) -> None:
    from app.engine.observer import NodeError

    with pytest.raises(NodeError) as exc:
        await build(raw).graph.ainvoke({"input": {"amount": "not a number"}})
    assert "amount: expected number" in exc.value.message


@pytest.mark.anyio
async def test_a_finished_run_does_not_leak_its_input_into_the_next_run_of_a_thread(
    raw: dict,
) -> None:
    from langgraph.checkpoint.memory import InMemorySaver

    from app.engine.compiler import compile_graph
    from app.engine.observer import NodeError

    graph, issues = parse_graph(raw)
    assert issues == []
    flow = compile_graph(graph, checkpointer=InMemorySaver())
    thread = {"configurable": {"thread_id": "studio-thread"}}

    first = await flow.graph.ainvoke({"input": {"amount": 5000, "tier": "gold"}}, thread)
    assert first["_output"] == {"amount": 5000, "tier": "gold"}

    with pytest.raises(NodeError) as exc:
        await flow.graph.ainvoke({"input": {}}, thread)
    assert "amount: required" in exc.value.message

    third = await flow.graph.ainvoke({"input": {"amount": 1}}, thread)
    assert third["_output"] == {"amount": 1, "tier": "silver"}
