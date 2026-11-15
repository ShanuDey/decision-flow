import httpx
import pytest

from app.engine.graph import Graph
from app.engine.nodes import NODE_TYPES
from app.engine.validate import parse_graph
from app.flows.format import flow_format
from app.templates.service import load_templates

pytestmark = pytest.mark.anyio


async def test_the_format_needs_a_sign_in(anon_client: httpx.AsyncClient) -> None:
    assert (await anon_client.get("/flow-format")).status_code == 401


async def test_the_format_lists_every_node_type_and_explains_each(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/flow-format")
    assert response.status_code == 200
    body = response.json()
    names = [node.type_name() for node in NODE_TYPES]
    assert body["node_types"] == names
    for name in names:
        assert f"`{name}`" in body["guide"], f"the guide does not explain the {name} node"


async def test_the_schema_is_the_graph_schema(client: httpx.AsyncClient) -> None:
    body = (await client.get("/flow-format")).json()
    assert body["graph_schema"] == Graph.model_json_schema()
    assert "nodes" in body["graph_schema"]["properties"]


async def test_the_examples_are_the_templates_and_all_valid(client: httpx.AsyncClient) -> None:
    body = (await client.get("/flow-format")).json()
    assert [e["id"] for e in body["examples"]] == [t.id for t in load_templates()]
    for example in body["examples"]:
        graph, issues = parse_graph(example["draft"])
        assert graph is not None and not issues, example["id"]


async def test_the_guide_names_the_steps_an_agent_takes(client: httpx.AsyncClient) -> None:
    guide = (await client.get("/flow-format")).json()["guide"]
    for step in (
        "create_flow",
        "get_flow",
        "save_draft",
        "validate_flow",
        "publish_flow",
        "create_run",
    ):
        assert f"`{step}`" in guide, step
    assert "if_match" in guide and "draft_version" in guide


def test_the_format_is_built_once() -> None:
    assert flow_format() is flow_format()
