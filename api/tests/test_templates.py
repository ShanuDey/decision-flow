import httpx
import pytest

from app.engine.validate import parse_graph
from app.limits import Limits
from app.templates.service import load_templates


def test_every_template_is_valid_within_default_limits() -> None:
    limits = Limits()
    templates = load_templates()
    assert templates
    for template in templates:
        issues = parse_graph(template.draft, limits.max_nodes, limits.max_edges)[1]
        assert issues == [], template.id


def test_template_ids_are_unique() -> None:
    ids = [t.id for t in load_templates()]
    assert len(ids) == len(set(ids))


def test_inputs_and_outputs_come_from_the_draft() -> None:
    loan = next(t for t in load_templates() if t.id == "loan-eligibility")
    assert loan.inputs == ["income", "credit_score"]
    assert loan.outputs == ["decision"]
    assert loan.node_types == ["assign", "condition", "end", "start"]


@pytest.mark.anyio
async def test_list_templates_returns_drafts(client: httpx.AsyncClient) -> None:
    response = await client.get("/templates")
    assert response.status_code == 200
    items = response.json()["items"]
    assert {t["id"] for t in items} == {t.id for t in load_templates()}
    assert all(t["draft"]["nodes"] for t in items)


@pytest.mark.anyio
async def test_list_templates_is_stable_across_calls(client: httpx.AsyncClient) -> None:
    first = (await client.get("/templates")).json()
    second = (await client.get("/templates")).json()
    assert first == second


@pytest.mark.anyio
@pytest.mark.parametrize("template_id", [t.id for t in load_templates()])
async def test_template_draft_creates_a_flow(client: httpx.AsyncClient, template_id: str) -> None:
    items = (await client.get("/templates")).json()["items"]
    template = next(t for t in items if t["id"] == template_id)
    created = await client.post(
        "/flows", json={"name": template["title"], "draft": template["draft"]}
    )
    assert created.status_code == 201
    validated = await client.post(f"/flows/{created.json()['id']}/validate")
    assert validated.status_code == 200


@pytest.mark.anyio
async def test_list_templates_requires_auth() -> None:
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as anon:
        assert (await anon.get("/templates")).status_code == 401
