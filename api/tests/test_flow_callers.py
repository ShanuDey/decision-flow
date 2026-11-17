import uuid

import httpx
import pytest

from tests.conftest import create_flow
from tests.test_node_subflow import child_draft, parent_draft, publish

pytestmark = pytest.mark.anyio


async def published_child_and_parent(client: httpx.AsyncClient) -> tuple[dict, dict]:
    child = await create_flow(client, child_draft())
    await publish(client, child["id"])
    parent = await create_flow(client, parent_draft(child["id"]))
    await publish(client, parent["id"])
    return child, parent


async def test_callers_lists_flows_whose_published_version_calls_this_one(
    client: httpx.AsyncClient,
) -> None:
    child, parent = await published_child_and_parent(client)
    response = await client.get(f"/flows/{child['id']}/callers")
    assert response.status_code == 200
    assert response.json() == {"items": [{"id": parent["id"], "name": "Demo"}]}


async def test_a_flow_nobody_calls_has_no_callers(client: httpx.AsyncClient) -> None:
    _, parent = await published_child_and_parent(client)
    assert (await client.get(f"/flows/{parent['id']}/callers")).json() == {"items": []}


async def test_a_draft_that_is_not_published_is_not_a_caller(client: httpx.AsyncClient) -> None:
    child = await create_flow(client, child_draft())
    await publish(client, child["id"])
    await create_flow(client, parent_draft(child["id"]))
    assert (await client.get(f"/flows/{child['id']}/callers")).json() == {"items": []}


async def test_callers_of_an_unknown_flow_is_404(client: httpx.AsyncClient) -> None:
    assert (await client.get(f"/flows/{uuid.uuid4()}/callers")).status_code == 404


async def test_deleting_a_called_flow_is_refused_with_the_callers(
    client: httpx.AsyncClient,
) -> None:
    child, parent = await published_child_and_parent(client)
    response = await client.delete(f"/flows/{child['id']}")
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "flow_in_use"
    assert body["details"]["callers"] == [{"id": parent["id"], "name": "Demo"}]
    assert (await client.get(f"/flows/{child['id']}")).status_code == 200


async def test_force_deletes_a_called_flow_and_the_caller_then_fails_clearly(
    client: httpx.AsyncClient,
) -> None:
    child, parent = await published_child_and_parent(client)
    assert (await client.delete(f"/flows/{child['id']}?force=true")).status_code == 204
    assert (await client.get(f"/flows/{child['id']}")).status_code == 404
    run = await client.post(f"/flows/{parent['id']}/runs", json={"input": {"amount": 1}})
    assert run.json()["status"] == "failed"
    assert "no published version" in run.json()["error"]["message"]


async def test_deleting_a_flow_nobody_calls_needs_no_force(client: httpx.AsyncClient) -> None:
    _, parent = await published_child_and_parent(client)
    assert (await client.delete(f"/flows/{parent['id']}")).status_code == 204


async def test_deleting_an_unknown_flow_is_still_404(client: httpx.AsyncClient) -> None:
    assert (await client.delete(f"/flows/{uuid.uuid4()}")).status_code == 404


async def test_unpublishing_a_called_flow_is_refused_with_the_callers(
    client: httpx.AsyncClient,
) -> None:
    child, parent = await published_child_and_parent(client)
    response = await client.post(f"/flows/{child['id']}/unpublish")
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "flow_in_use"
    assert body["details"]["callers"] == [{"id": parent["id"], "name": "Demo"}]
    assert (await client.get(f"/flows/{child['id']}")).json()["published_version"] == 1


async def test_force_unpublishes_a_called_flow_and_the_caller_then_fails_clearly(
    client: httpx.AsyncClient,
) -> None:
    child, parent = await published_child_and_parent(client)
    assert (await client.post(f"/flows/{child['id']}/unpublish?force=true")).status_code == 200
    run = await client.post(f"/flows/{parent['id']}/runs", json={"input": {"amount": 1}})
    assert run.json()["status"] == "failed"


async def test_unpublishing_a_flow_nobody_calls_needs_no_force(client: httpx.AsyncClient) -> None:
    _, parent = await published_child_and_parent(client)
    assert (await client.post(f"/flows/{parent['id']}/unpublish")).status_code == 200
