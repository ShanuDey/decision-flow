import json
from pathlib import Path

import pytest

from app.engine.compiler import compile_graph
from app.engine.runtime import run_flow
from app.engine.validate import parse_graph
from tests.recorder import Recorder

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "flows" / "condition.json"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def raw() -> dict:
    return json.loads(EXAMPLE.read_text())


def issues(raw: dict) -> list:
    return parse_graph(raw)[1]


def codes(raw: dict) -> list[tuple[str, str | None]]:
    return [(i.code, i.node_id) for i in issues(raw)]


def condition(raw: dict) -> dict:
    return next(n for n in raw["nodes"] if n["type"] == "condition")


async def run(raw: dict, payload: dict, observer=None):
    graph, found = parse_graph(raw)
    assert found == []
    return await run_flow(compile_graph(graph), payload, observer)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("payload", "decision"),
    [
        ({"income": 50000, "credit_score": 700}, "approved"),
        ({"income": 50000, "credit_score": 500}, "declined"),
        ({"income": 10000, "credit_score": 700}, "declined"),
    ],
)
async def test_the_flow_follows_the_branch_the_expression_picks(
    raw: dict, payload: dict, decision: str
) -> None:
    result = await run(raw, payload)
    assert result.status == "succeeded"
    assert result.output == {"decision": decision}


@pytest.mark.anyio
async def test_the_expression_and_result_are_the_nodes_recorded_output(raw: dict) -> None:
    recorder = Recorder()
    await run(raw, {"income": 40000, "credit_score": 650}, recorder)
    assert recorder.node_outputs["eligible"] == {
        "expression": "input.income >= 30000 && input.credit_score >= 600",
        "result": True,
    }


@pytest.mark.anyio
async def test_a_condition_can_read_an_upstream_nodes_output(raw: dict) -> None:
    condition(raw)["data"]["expression"] = "nodes.start.output.income > 100"
    assert (await run(raw, {"income": 500, "credit_score": 1})).output == {"decision": "approved"}


def test_a_non_boolean_expression_is_rejected_at_design_time(raw: dict) -> None:
    condition(raw)["data"]["expression"] = "input.income + 1"
    [issue] = issues(raw)
    assert (issue.code, issue.node_id, issue.field) == (
        "expression_not_boolean",
        "eligible",
        "data.expression",
    )


@pytest.mark.anyio
async def test_a_dynamic_non_boolean_result_fails_the_run_at_the_condition(raw: dict) -> None:
    raw["nodes"][0]["data"]["inputs"].append({"name": "note", "type": "string", "required": True})
    condition(raw)["data"]["expression"] = "input.note"
    result = await run(raw, {"income": 1, "credit_score": 1, "note": "hi"})
    assert result.status == "failed"
    assert result.error.node_id == "eligible"


@pytest.mark.anyio
async def test_a_missing_value_fails_the_run_at_the_condition(raw: dict) -> None:
    condition(raw)["data"]["expression"] = "nodes.start.output.ghost > 1"
    result = await run(raw, {"income": 1, "credit_score": 1})
    assert result.status == "failed"
    assert result.error.node_id == "eligible"
    assert "ghost" in result.error.message


def test_a_syntax_error_is_reported_on_the_expression_field(raw: dict) -> None:
    condition(raw)["data"]["expression"] = "input.income >"
    [issue] = issues(raw)
    assert (issue.code, issue.node_id, issue.field) == (
        "invalid_expression",
        "eligible",
        "data.expression",
    )


def test_an_unknown_input_or_variable_is_rejected(raw: dict) -> None:
    condition(raw)["data"]["expression"] = "input.ghost > 1 && vars.nope == 'x'"
    assert codes(raw) == [("unknown_reference", "eligible")] * 2


def test_reading_a_node_that_does_not_exist_is_rejected(raw: dict) -> None:
    condition(raw)["data"]["expression"] = "nodes.ghost.output.x > 1"
    assert codes(raw) == [("unknown_reference", "eligible")]


def test_a_node_has_only_an_output_to_read(raw: dict) -> None:
    condition(raw)["data"]["expression"] = "nodes.start.ouptut.income > 1"
    [issue] = issues(raw)
    assert (issue.code, issue.node_id) == ("unknown_reference", "eligible")
    assert "only has 'output'" in issue.message


def test_reading_a_node_that_runs_later_or_on_another_branch_is_rejected(raw: dict) -> None:
    condition(raw)["data"]["expression"] = "nodes.approve.output.decision == 'x'"
    assert codes(raw) == [("not_upstream", "eligible")]


def test_both_branches_need_an_edge(raw: dict) -> None:
    raw["edges"] = [e for e in raw["edges"] if e["id"] != "e3"]
    found = issues(raw)
    assert [(i.code, i.node_id, i.field) for i in found] == [
        ("missing_branch", "eligible", "false"),
        ("unreachable", "decline", None),
    ]


def test_an_edge_from_an_unknown_handle_is_rejected(raw: dict) -> None:
    next(e for e in raw["edges"] if e["id"] == "e3")["sourceHandle"] = "maybe"
    assert [i.code for i in issues(raw)] == ["invalid_handle", "missing_branch"]


def test_a_branch_cannot_fan_out(raw: dict) -> None:
    raw["edges"].append(
        {"id": "e6", "source": "eligible", "target": "decline", "sourceHandle": "true"}
    )
    assert [i.code for i in issues(raw)] == ["parallel_not_supported"]
