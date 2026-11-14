import httpx
import pytest

from tests.auth_helpers import bearer
from tests.conftest import FakeFlowStore, FakeRunStore, FakeWorkspaceStore, create_flow

pytestmark = pytest.mark.anyio

OTHER = bearer(sub="user-2")


async def test_a_users_first_request_creates_one_member_and_later_ones_reuse_it(
    client: httpx.AsyncClient, workspace_store: FakeWorkspaceStore
) -> None:
    await client.get("/flows")
    await client.get("/flows")
    assert len(workspace_store.members) == 1


async def test_flows_are_stamped_with_the_creator_and_their_workspace(
    client: httpx.AsyncClient, flow_store: FakeFlowStore, workspace_store: FakeWorkspaceStore
) -> None:
    created = await create_flow(client)
    (member,) = workspace_store.members.values()
    flow = next(iter(flow_store.flows.values()))
    assert str(flow.id) == created["id"]
    assert (flow.workspace_id, flow.created_by, flow.updated_by) == (
        member.workspace_id,
        member.user_id,
        member.user_id,
    )


async def test_another_workspace_cannot_see_or_change_a_flow(client: httpx.AsyncClient) -> None:
    flow = await create_flow(client)
    url = f"/flows/{flow['id']}"

    assert (await client.get(url, headers=OTHER)).status_code == 404
    assert (await client.patch(url, json={"name": "x"}, headers=OTHER)).status_code == 404
    assert (await client.post(f"{url}/validate", headers=OTHER)).status_code == 404
    saved = await client.put(f"{url}/draft", json={}, headers={**OTHER, "If-Match": "1"})
    assert saved.status_code == 404

    assert (await client.get("/flows", headers=OTHER)).json()["items"] == []
    assert (await client.get(url)).status_code == 200
    assert (await client.get("/flows")).json()["total"] == 1


async def test_another_workspace_cannot_run_a_flow_or_read_its_runs(
    client: httpx.AsyncClient, run_store: FakeRunStore
) -> None:
    flow = await create_flow(client)
    ran = await client.post(f"/flows/{flow['id']}/runs", json={"test": True, "input": {}})
    assert ran.status_code == 200
    run_id = ran.json()["run_id"]

    blocked = await client.post(
        f"/flows/{flow['id']}/runs", json={"test": True, "input": {}}, headers=OTHER
    )
    assert blocked.status_code == 404
    assert (await client.get(f"/runs/{run_id}", headers=OTHER)).status_code == 404
    assert (await client.get("/runs", headers=OTHER)).json()["items"] == []
    assert len((await client.get("/runs")).json()["items"]) == 1
    assert len(run_store.runs) == 1


async def test_runs_are_stamped_with_the_caller_and_their_workspace(
    client: httpx.AsyncClient, run_store: FakeRunStore, workspace_store: FakeWorkspaceStore
) -> None:
    flow = await create_flow(client)
    await client.post(f"/flows/{flow['id']}/runs", json={"test": True, "input": {}})
    (member,) = workspace_store.members.values()
    (run,) = run_store.runs.values()
    assert (run.workspace_id, run.created_by) == (member.workspace_id, member.user_id)
