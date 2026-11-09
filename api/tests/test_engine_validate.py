import copy
import json
from pathlib import Path

import pytest

from app.engine.validate import parse_graph

FIXTURE = Path(__file__).resolve().parents[2] / "examples" / "flows" / "start-end.json"


@pytest.fixture
def raw() -> dict:
    return json.loads(FIXTURE.read_text())


def codes(raw: dict) -> list[str]:
    return [i.code for i in parse_graph(raw)[1]]


def test_golden_fixture_is_valid(raw: dict) -> None:
    graph, issues = parse_graph(raw)
    assert issues == []
    assert graph is not None
    assert [n.id for n in graph.nodes] == ["start", "end"]


def test_unknown_node_type_is_a_schema_issue_naming_the_node(raw: dict) -> None:
    raw["nodes"][1]["type"] = "teleport"
    graph, issues = parse_graph(raw)
    assert graph is None
    assert issues[0].code == "schema"
    assert issues[0].node_id == "end"


def test_extra_field_is_rejected(raw: dict) -> None:
    raw["nodes"][0]["data"]["inputz"] = []
    assert codes(raw) == ["schema"]


def test_enum_without_values_fails(raw: dict) -> None:
    del raw["nodes"][0]["data"]["inputs"][1]["values"]
    assert codes(raw) == ["schema"]


def test_schema_errors_stop_before_structure_checks(raw: dict) -> None:
    raw["nodes"][0]["type"] = "nope"
    raw["edges"] = []
    assert codes(raw) == ["schema"]


def test_needs_exactly_one_start(raw: dict) -> None:
    extra = copy.deepcopy(raw["nodes"][0])
    extra.update(id="start_2", name="Start 2")
    raw["nodes"].append(extra)
    assert "start_count" in codes(raw)


def test_needs_an_end(raw: dict) -> None:
    raw["nodes"].pop(1)
    raw["edges"] = []
    assert "end_missing" in codes(raw)


@pytest.mark.parametrize("bad_id", ["input", "vars", "Start", "1abc", "a-b", "x" * 41])
def test_bad_ids(raw: dict, bad_id: str) -> None:
    raw["nodes"][0]["id"] = bad_id
    raw["edges"][0]["source"] = bad_id
    assert set(codes(raw)) & {"reserved_id", "bad_id"}


def test_duplicate_id_and_name(raw: dict) -> None:
    raw["nodes"][1]["id"] = "start"
    raw["nodes"][1]["name"] = "Start"
    assert {"duplicate_id", "duplicate_name"} <= set(codes(raw))


def test_name_defaults_to_type_for_uniqueness(raw: dict) -> None:
    del raw["nodes"][0]["name"]
    raw["nodes"][1]["name"] = "start"
    assert "duplicate_name" in codes(raw)


def test_dangling_edge(raw: dict) -> None:
    raw["edges"][0]["target"] = "ghost"
    issues = parse_graph(raw)[1]
    assert [i.code for i in issues] == ["dangling_edge"]
    assert issues[0].field == "edges.e1.target"


def test_start_cannot_have_incoming_and_end_cannot_have_outgoing(raw: dict) -> None:
    raw["edges"].append({"id": "e2", "source": "end", "target": "start"})
    assert {"start_has_incoming", "end_has_outgoing"} <= set(codes(raw))


def test_cycle_is_rejected() -> None:
    node = lambda i, t: {"id": i, "type": t, "data": {}}  # noqa: E731
    raw = {
        "schema_version": 1,
        "nodes": [node("start", "start"), node("end", "end")],
        "edges": [{"id": "e1", "source": "start", "target": "end"}],
    }
    assert codes(raw) == []
    # a self-loop on start is the smallest cycle
    raw["edges"].append({"id": "e2", "source": "start", "target": "start"})
    assert "cycle" in codes(raw)


def test_unreachable_node(raw: dict) -> None:
    raw["nodes"].append(
        {"id": "orphan", "type": "end", "name": "Orphan", "data": raw["nodes"][1]["data"]}
    )
    assert "unreachable" in codes(raw)


def test_start_with_no_outgoing_edge(raw: dict) -> None:
    raw["edges"] = []
    found = set(codes(raw))
    assert "no_outgoing_edge" in found


def test_end_nodes_must_declare_same_outputs(raw: dict) -> None:
    second = copy.deepcopy(raw["nodes"][1])
    second.update(id="end_2", name="End 2")
    second["data"]["outputs"] = [{"name": "other", "type": "string", "value": "x"}]
    raw["nodes"].append(second)
    raw["edges"].append({"id": "e2", "source": "start", "target": "end_2"})
    assert "end_outputs_differ" in codes(raw)


def test_duplicate_variable(raw: dict) -> None:
    raw["variables"] = [{"name": "x", "type": "number"}, {"name": "x", "type": "string"}]
    assert "duplicate_variable" in codes(raw)


def test_end_output_referencing_undeclared_input_or_variable(raw: dict) -> None:
    raw["nodes"][1]["data"]["outputs"][0]["value"] = "{{ input.ghost }}"
    raw["nodes"][1]["data"]["outputs"][1]["value"] = "{{ vars.ghost }}"
    issues = parse_graph(raw)[1]
    assert [i.code for i in issues] == ["unknown_reference", "unknown_reference"]
    assert issues[0].node_id == "end"
    assert issues[0].field == "data.outputs.amount.value"


def test_unsupported_expression_is_reported_with_node_and_field(raw: dict) -> None:
    raw["nodes"][1]["data"]["outputs"][0]["value"] = "{{ input.amount > 1 }}"
    issue = parse_graph(raw)[1][0]
    assert (issue.code, issue.node_id) == ("unsupported_expression", "end")


def test_enum_output_needs_values(raw: dict) -> None:
    del raw["nodes"][1]["data"]["outputs"][1]["values"]
    assert codes(raw) == ["schema"]
