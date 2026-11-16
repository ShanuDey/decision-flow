import json
from pathlib import Path
from typing import Any, Literal

import pytest
from pydantic import Field

from app.engine.compiler import compile_graph
from app.engine.graph import Edge, Graph
from app.engine.nodes import NodeContext, NodeModel
from app.engine.run_secrets import RunSecrets, referenced_secret_names
from app.engine.runtime import run_flow
from app.engine.validate import check_settings, parse_graph
from tests.recorder import Recorder

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "flows"
VALUE = "s3cret-value-123"


class Probe(NodeModel):
    """Stands in for a node that accepts secrets; the real one arrives with the HTTP node."""

    type: Literal["probe"] = "probe"
    url: str = ""
    header: str = ""
    seen: list[dict[str, str]] = Field(default_factory=list)

    def templates(self) -> dict[str, str]:
        return {"url": self.url, "header": self.header}

    def secret_fields(self) -> set[str]:
        return {"header"}

    async def run(self, state: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        self.seen.append(ctx.secrets.as_scope())
        return {}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def raw(name: str = "assign-variable.json") -> dict:
    return json.loads((EXAMPLES / name).read_text())


def codes(data: dict) -> list[str]:
    return [i.code for i in parse_graph(data)[1]]


def graph_with(probe: Probe) -> Graph:
    base, _ = parse_graph(raw("start-end.json"))
    assert base is not None
    start, end = base.nodes
    edges = [
        Edge(id="e1", source=start.id, target=probe.id),
        Edge(id="e2", source=probe.id, target=end.id),
    ]
    return Graph.model_construct(
        schema_version=1, variables=[], nodes=[start, probe, end], edges=edges
    )


def test_assign_refuses_a_secret() -> None:
    data = raw()
    assign = next(n for n in data["nodes"] if n["type"] == "assign")
    assign["data"]["assignments"][1]["value"] = "{{ secrets.API_KEY }}"

    graph, issues = parse_graph(data)
    assert graph is None
    assert [(i.code, i.node_id, i.field) for i in issues] == [
        ("secret_not_allowed", "assign_values", "data.assignments.1.value")
    ]
    assert "secrets.API_KEY" in issues[0].message


def test_end_refuses_a_secret() -> None:
    data = raw("start-end.json")
    end = next(n for n in data["nodes"] if n["type"] == "end")
    end["data"]["outputs"] = [{"name": "k", "type": "string", "value": "{{ secrets.API_KEY }}"}]

    assert codes(data) == ["secret_not_allowed"]


def test_a_condition_expression_cannot_read_a_secret() -> None:
    data = raw("condition.json")
    condition = next(n for n in data["nodes"] if n["type"] == "condition")
    condition["data"]["expression"] = 'secrets.API_KEY == "x"'

    graph, issues = parse_graph(data)
    assert graph is None and issues


def test_a_marked_field_accepts_a_secret_and_an_unmarked_one_does_not() -> None:
    probe = Probe(id="probe", header="Bearer {{ secrets.API_KEY }}", url="{{ secrets.API_KEY }}")

    issues = check_settings(graph_with(probe))

    assert [(i.code, i.field) for i in issues] == [("secret_not_allowed", "url")]


def test_a_secret_is_one_value() -> None:
    probe = Probe(id="probe", header="{{ secrets.API_KEY.inner }}")

    assert [i.code for i in check_settings(graph_with(probe))] == ["unknown_reference"]


def test_an_unknown_secret_name_is_not_a_validation_error() -> None:
    probe = Probe(id="probe", header="{{ secrets.NEVER_ADDED }}")

    assert check_settings(graph_with(probe)) == []


def test_only_names_in_marked_fields_are_loaded() -> None:
    probe = Probe(
        id="probe",
        header="a {{ secrets.ONE }} b {{ secrets.TWO }} {{ vars.x }}",
        url="{{ secrets.IGNORED }}",
    )

    assert referenced_secret_names(graph_with(probe)) == {"ONE", "TWO"}
    assert referenced_secret_names(parse_graph(raw())[0]) == set()


@pytest.mark.anyio
async def test_each_run_gets_its_own_secrets_and_they_stay_out_of_every_record() -> None:
    probe = Probe(id="probe", header="{{ secrets.API_KEY }}")
    flow = compile_graph(graph_with(probe))
    recorder = Recorder()

    first = await run_flow(
        flow, {"amount": 5}, recorder, secrets=RunSecrets(values={"API_KEY": VALUE})
    )
    second = await run_flow(flow, {"amount": 5})

    assert first.status == second.status == "succeeded"
    assert probe.seen == [{"API_KEY": VALUE}, {}]
    assert VALUE not in str(vars(recorder)) and VALUE not in first.model_dump_json()


def test_run_secrets_never_print_their_values() -> None:
    secrets = RunSecrets(values={"API_KEY": VALUE})

    assert VALUE not in repr(secrets) and VALUE not in str(secrets)
    assert VALUE not in secrets.model_dump_json()
