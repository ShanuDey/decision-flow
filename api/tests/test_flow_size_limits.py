from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from app.engine.validate import parse_graph
from app.flows.service import blank_draft
from app.limits import Limits, get_limits
from app.main import app
from tests.conftest import create_flow

pytestmark = pytest.mark.anyio


def limits(**fields: int | str) -> Limits:
    return Limits(_env_file=None, **fields)


def padded(nodes: int = 0, edges: int = 0) -> dict[str, Any]:
    """A draft with junk entries; the size check runs before any parsing."""
    draft = blank_draft()
    draft["nodes"] += [{"id": f"n{i}"} for i in range(nodes)]
    draft["edges"] += [{"id": f"x{i}"} for i in range(edges)]
    return draft


@pytest.fixture
def override() -> Iterator[None]:
    yield
    app.dependency_overrides.pop(get_limits, None)


def test_defaults() -> None:
    fresh = limits()
    assert (fresh.max_nodes, fresh.max_edges, fresh.max_flows_per_user) == (50, 100, 20)
    assert fresh.max_versions_per_flow == 0


def test_at_the_cap_passes_and_one_over_is_refused() -> None:
    assert parse_graph(blank_draft(), max_nodes=2, max_edges=1)[1] == []
    _, issues = parse_graph(padded(nodes=1), max_nodes=2)
    assert [(i.code, i.field) for i in issues] == [("too_many_nodes", "nodes")]
    assert issues[0].message == "flow has 3 nodes; the limit is 2"
    _, issues = parse_graph(padded(edges=1), max_edges=1)
    assert [i.code for i in issues] == ["too_many_edges"]


def test_zero_turns_a_cap_off() -> None:
    _, issues = parse_graph(padded(nodes=500, edges=500))
    assert not any(i.code.startswith("too_many") for i in issues)


def test_both_caps_are_reported_together() -> None:
    _, issues = parse_graph(padded(nodes=1, edges=1), max_nodes=2, max_edges=1)
    assert sorted(i.code for i in issues) == ["too_many_edges", "too_many_nodes"]


@pytest.mark.usefixtures("override")
async def test_validate_and_run_return_the_same_error(client: httpx.AsyncClient) -> None:
    app.dependency_overrides[get_limits] = lambda: limits(max_nodes=2)
    flow = await create_flow(client, padded(nodes=1))

    validated = await client.post(f"/flows/{flow['id']}/validate")
    ran = await client.post(f"/flows/{flow['id']}/runs", json={"test": True, "input": {}})

    assert validated.status_code == ran.status_code == 422
    assert validated.json() == ran.json()
    assert validated.json()["code"] == "invalid_flow"
    assert validated.json()["details"]["errors"][0]["code"] == "too_many_nodes"


@pytest.mark.usefixtures("override")
async def test_an_oversized_draft_still_saves(client: httpx.AsyncClient) -> None:
    app.dependency_overrides[get_limits] = lambda: limits(max_nodes=2)
    flow = await create_flow(client)
    saved = await client.put(
        f"/flows/{flow['id']}/draft", json=padded(nodes=5), headers={"If-Match": "1"}
    )
    assert saved.status_code == 200


@pytest.mark.usefixtures("override")
async def test_flow_cap_refuses_the_next_flow_with_the_notice(client: httpx.AsyncClient) -> None:
    app.dependency_overrides[get_limits] = lambda: limits(
        max_flows_per_user=2, limit_notice="Free demo."
    )
    await create_flow(client)
    await create_flow(client)

    refused = await client.post("/flows", json={"name": "Third"})
    assert refused.status_code == 409
    body = refused.json()
    assert body["code"] == "flow_limit_reached"
    assert body["details"] == {"limit": 2, "count": 2, "notice": "Free demo."}


@pytest.mark.usefixtures("override")
async def test_flow_cap_zero_is_unlimited(client: httpx.AsyncClient) -> None:
    app.dependency_overrides[get_limits] = lambda: limits(max_flows_per_user=0)
    for _ in range(3):
        await create_flow(client)


async def edit_and_publish(client: httpx.AsyncClient, flow: dict, times: int) -> None:
    for i in range(times):
        current = (await client.get(f"/flows/{flow['id']}")).json()
        draft = {**current["draft"], "nodes": [dict(n) for n in current["draft"]["nodes"]]}
        draft["nodes"][0]["name"] = f"Begin {i}"
        saved = await client.put(
            f"/flows/{flow['id']}/draft",
            json=draft,
            headers={"If-Match": str(current["draft_version"])},
        )
        assert saved.status_code == 200
        assert (await client.post(f"/flows/{flow['id']}/publish")).status_code == 201


async def version_numbers(client: httpx.AsyncClient, flow: dict) -> tuple[list[int], int]:
    body = (await client.get(f"/flows/{flow['id']}/versions")).json()
    return [v["version"] for v in body["items"]], body["keep_latest"]


@pytest.mark.usefixtures("override")
async def test_the_version_window_drops_the_oldest_and_keeps_counting(
    client: httpx.AsyncClient,
) -> None:
    app.dependency_overrides[get_limits] = lambda: limits(max_versions_per_flow=3)
    flow = await create_flow(client)
    await edit_and_publish(client, flow, 5)
    assert await version_numbers(client, flow) == ([5, 4, 3], 3)
    assert (await client.get(f"/flows/{flow['id']}/versions/2")).status_code == 404
    assert (await client.get(f"/flows/{flow['id']}")).json()["published_version"] == 5


@pytest.mark.usefixtures("override")
async def test_a_window_of_one_keeps_only_the_latest(client: httpx.AsyncClient) -> None:
    app.dependency_overrides[get_limits] = lambda: limits(max_versions_per_flow=1)
    flow = await create_flow(client)
    await edit_and_publish(client, flow, 3)
    assert await version_numbers(client, flow) == ([3], 1)


@pytest.mark.usefixtures("override")
async def test_a_zero_window_keeps_every_version(client: httpx.AsyncClient) -> None:
    app.dependency_overrides[get_limits] = lambda: limits(max_versions_per_flow=0)
    flow = await create_flow(client)
    await edit_and_publish(client, flow, 4)
    assert await version_numbers(client, flow) == ([4, 3, 2, 1], 0)


@pytest.mark.usefixtures("override")
async def test_an_unchanged_draft_is_a_conflict_even_when_it_is_now_too_big(
    client: httpx.AsyncClient,
) -> None:
    flow = await create_flow(client)
    assert (await client.post(f"/flows/{flow['id']}/publish")).status_code == 201
    app.dependency_overrides[get_limits] = lambda: limits(max_nodes=1)
    again = await client.post(f"/flows/{flow['id']}/publish")
    assert again.status_code == 409 and again.json()["code"] == "nothing_to_publish"
