import uuid

import httpx
import pytest

from tests.conftest import create_flow, example


@pytest.mark.anyio
async def test_create_without_draft_gives_a_valid_blank_flow(client: httpx.AsyncClient) -> None:
    flow = await create_flow(client)
    assert flow["draft_version"] == 1
    assert (await client.post(f"/flows/{flow['id']}/validate")).json() == {"valid": True}


@pytest.mark.anyio
async def test_list_and_get(client: httpx.AsyncClient) -> None:
    flow = await create_flow(client)
    listed = (await client.get("/flows", params={"q": "dem"})).json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == flow["id"]
    assert "draft" not in listed["items"][0]
    assert (await client.get(f"/flows/{flow['id']}")).json()["draft"] == flow["draft"]
    missing = await client.get(f"/flows/{uuid.uuid4()}")
    assert missing.status_code == 404 and missing.json()["code"] == "not_found"


@pytest.mark.anyio
async def test_save_draft_bumps_version_and_rejects_stale(client: httpx.AsyncClient) -> None:
    flow = await create_flow(client)
    url = f"/flows/{flow['id']}/draft"
    saved = await client.put(url, json=example("start-end.json"), headers={"If-Match": "1"})
    assert saved.status_code == 200 and saved.json() == {"draft_version": 2}
    stale = await client.put(url, json=example("start-end.json"), headers={"If-Match": "1"})
    assert stale.status_code == 409
    assert stale.json()["code"] == "draft_conflict"
    assert stale.json()["details"] == {"draft_version": 2}


@pytest.mark.anyio
async def test_save_draft_requires_if_match(client: httpx.AsyncClient) -> None:
    flow = await create_flow(client)
    response = await client.put(f"/flows/{flow['id']}/draft", json={})
    assert response.status_code == 428


@pytest.mark.anyio
async def test_save_draft_on_missing_flow_is_404(client: httpx.AsyncClient) -> None:
    response = await client.put(f"/flows/{uuid.uuid4()}/draft", json={}, headers={"If-Match": "1"})
    assert response.status_code == 404


@pytest.mark.anyio
async def test_an_invalid_draft_is_saved_but_fails_validation(client: httpx.AsyncClient) -> None:
    flow = await create_flow(client)
    broken = example("assign-variable.json")
    broken["nodes"][1]["data"]["assignments"][0]["variable"] = "totl"
    saved = await client.put(f"/flows/{flow['id']}/draft", json=broken, headers={"If-Match": "1"})
    assert saved.status_code == 200
    response = await client.post(f"/flows/{flow['id']}/validate")
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_flow"
    assert body["details"]["node_id"] == "assign_values"
    assert body["details"]["errors"]
