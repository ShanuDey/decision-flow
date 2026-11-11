import json
from pathlib import Path

import pytest

from app.engine.compiler import compile_graph
from app.engine.runtime import run_flow
from app.engine.validate import parse_graph

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "flows" / "assign-variable.json"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def raw() -> dict:
    return json.loads(EXAMPLE.read_text())


def issues(raw: dict) -> list:
    return parse_graph(raw)[1]


def assign_node(raw: dict) -> dict:
    return next(n for n in raw["nodes"] if n["type"] == "assign")


async def run(raw: dict, payload: dict):
    graph, found = parse_graph(raw)
    assert found == []
    return await run_flow(compile_graph(graph), payload)


@pytest.mark.anyio
async def test_example_assigns_typed_values_and_later_assignments_see_earlier_ones(
    raw: dict,
) -> None:
    result = await run(raw, {"amount": 5000})
    assert result.status == "succeeded"
    assert result.output == {"total": 5000, "label": "Order total 5000"}
    assert isinstance(result.output["total"], int)  # a lone reference keeps its type


@pytest.mark.anyio
async def test_variables_the_node_does_not_assign_keep_their_initial_value(raw: dict) -> None:
    raw["variables"].append({"name": "untouched", "type": "string", "initial": "kept"})
    raw["nodes"][-1]["data"]["outputs"] = [
        {"name": "u", "type": "string", "value": "{{ vars.untouched }}"}
    ]
    assert (await run(raw, {"amount": 1})).output == {"u": "kept"}


def test_assigning_an_undeclared_variable_is_rejected_naming_node_and_field(raw: dict) -> None:
    assign_node(raw)["data"]["assignments"][0]["variable"] = "totl"
    [issue] = issues(raw)
    assert issue.code == "unknown_variable"
    assert (issue.node_id, issue.field) == ("assign_values", "data.assignments.0.variable")


def test_a_typo_in_a_vars_reference_fails_validation(raw: dict) -> None:
    assign_node(raw)["data"]["assignments"][1]["value"] = "Order total {{ vars.totl }}"
    [issue] = issues(raw)
    assert issue.code == "unknown_reference"
    assert (issue.node_id, issue.field) == ("assign_values", "data.assignments.1.value")


def test_unknown_input_and_unsupported_expressions_fail_validation(raw: dict) -> None:
    assign_node(raw)["data"]["assignments"][0]["value"] = "{{ input.ghost }}"
    assign_node(raw)["data"]["assignments"][1]["value"] = "{{ input.amount > 1 }}"
    assert [i.code for i in issues(raw)] == ["unknown_reference", "unsupported_expression"]


@pytest.mark.anyio
async def test_a_value_of_the_wrong_type_fails_the_run_at_the_assign_node(raw: dict) -> None:
    assign_node(raw)["data"]["assignments"][0]["value"] = "not a number"
    result = await run(raw, {"amount": 1})
    assert result.status == "failed"
    assert result.error.node_id == "assign_values"
    assert result.error.message == "assignment 'total': expected number"


@pytest.mark.anyio
async def test_enum_variables_only_accept_their_values(raw: dict) -> None:
    raw["variables"].append(
        {"name": "tier", "type": "enum", "values": ["silver", "gold"], "initial": "silver"}
    )
    assign_node(raw)["data"]["assignments"].append({"variable": "tier", "value": "bronze"})
    result = await run(raw, {"amount": 1})
    assert result.error.node_id == "assign_values"
    assert "must be one of ['silver', 'gold']" in result.error.message


def test_an_enum_variable_needs_values(raw: dict) -> None:
    raw["variables"].append({"name": "tier", "type": "enum", "initial": "silver"})
    assert [i.code for i in issues(raw)] == ["schema"]


def test_an_initial_value_must_match_the_variable_type(raw: dict) -> None:
    raw["variables"].append({"name": "count", "type": "number", "initial": "zero"})
    [issue] = issues(raw)
    assert issue.code == "invalid_initial"
    assert "expected number" in issue.message


def test_a_variable_name_must_be_referenceable_from_templates(raw: dict) -> None:
    raw["variables"].append({"name": "my-var", "type": "string"})
    assert [i.code for i in issues(raw)] == ["invalid_variable_name"]


@pytest.mark.anyio
async def test_structured_values_render_as_json_inside_text_and_keep_type_alone(
    raw: dict,
) -> None:
    raw["variables"] += [
        {"name": "items", "type": "array", "initial": [1, 2]},
        {"name": "copy", "type": "array"},
        {"name": "text", "type": "string"},
    ]
    assign_node(raw)["data"]["assignments"] += [
        {"variable": "copy", "value": "{{ vars.items }}"},
        {"variable": "text", "value": "items={{ vars.items }}"},
    ]
    raw["nodes"][-1]["data"]["outputs"] = [
        {"name": "copy", "type": "array", "value": "{{ vars.copy }}"},
        {"name": "text", "type": "string", "value": "{{ vars.text }}"},
    ]
    assert (await run(raw, {"amount": 1})).output == {"copy": [1, 2], "text": "items=[1, 2]"}


@pytest.mark.anyio
async def test_reading_a_variable_with_no_value_fails_the_run(raw: dict) -> None:
    raw["variables"].append({"name": "unset", "type": "string"})
    assign_node(raw)["data"]["assignments"].append(
        {"variable": "unset", "value": "{{ vars.unset.x }}"}
    )
    result = await run(raw, {"amount": 1})
    assert result.status == "failed"
    assert result.error.node_id == "assign_values"


@pytest.mark.anyio
async def test_the_assigned_values_are_the_nodes_recorded_output(raw: dict) -> None:
    class Recorder:
        outputs: dict = {}

        async def run_started(self, inputs): ...
        async def node_started(self, node, inputs): ...
        async def node_finished(self, node, status, duration_ms, error, outputs=None):
            self.outputs[node.id] = outputs

        async def run_finished(self, status, error, outputs=None): ...

    graph, _ = parse_graph(raw)
    recorder = Recorder()
    await run_flow(compile_graph(graph), {"amount": 7}, recorder)
    assert recorder.outputs["assign_values"] == {"total": 7, "label": "Order total 7"}
