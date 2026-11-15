from collections.abc import Iterator

import httpx
import pytest

from app.limits import Limits, get_limits
from app.main import app
from app.settings import Settings, get_settings
from tests.conftest import FakeFlowStore, create_flow
from tests.test_flow_size_limits import edit_and_publish, version_numbers

pytestmark = pytest.mark.anyio


@pytest.fixture
def soft() -> Iterator[None]:
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, delete_mode="soft")
    yield
    app.dependency_overrides.pop(get_settings, None)
    app.dependency_overrides.pop(get_limits, None)


def test_deleting_is_soft_by_default() -> None:
    assert Settings(_env_file=None).delete_mode == "soft"


async def test_config_reports_the_mode(client: httpx.AsyncClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, delete_mode="hard")
    try:
        assert (await client.get("/config")).json() == {"delete_mode": "hard"}
    finally:
        app.dependency_overrides.pop(get_settings, None)


async def test_config_reports_soft(client: httpx.AsyncClient) -> None:
    assert (await client.get("/config")).json() == {"delete_mode": "soft"}


@pytest.fixture
def hard() -> Iterator[None]:
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, delete_mode="hard")
    yield
    app.dependency_overrides.pop(get_settings, None)


@pytest.mark.usefixtures("hard")
async def test_hard_delete_removes_the_row(
    client: httpx.AsyncClient, flow_store: FakeFlowStore
) -> None:
    flow = await create_flow(client)
    assert (await client.delete(f"/flows/{flow['id']}")).status_code == 204
    assert flow_store.flows == {}


@pytest.mark.usefixtures("soft")
async def test_soft_delete_hides_the_flow_but_keeps_the_row(
    client: httpx.AsyncClient, flow_store: FakeFlowStore
) -> None:
    flow = await create_flow(client)
    assert (await client.delete(f"/flows/{flow['id']}")).status_code == 204

    assert (await client.get(f"/flows/{flow['id']}")).status_code == 404
    assert (await client.get("/flows")).json()["total"] == 0
    assert (await client.delete(f"/flows/{flow['id']}")).status_code == 404
    assert (await client.post(f"/flows/{flow['id']}/runs", json={"test": True})).status_code == 404
    assert (await client.post(f"/flows/{flow['id']}/publish")).status_code == 404
    (kept,) = flow_store.flows.values()
    assert kept.deleted_at is not None and kept.deleted_by == kept.created_by


@pytest.mark.usefixtures("soft")
async def test_a_soft_deleted_flow_frees_its_slot_under_the_cap(client: httpx.AsyncClient) -> None:
    app.dependency_overrides[get_limits] = lambda: Limits(_env_file=None, max_flows_per_user=1)
    flow = await create_flow(client)
    assert (await client.post("/flows", json={"name": "Two"})).status_code == 409
    await client.delete(f"/flows/{flow['id']}")
    assert (await client.post("/flows", json={"name": "Two"})).status_code == 201


@pytest.mark.usefixtures("soft")
async def test_runs_of_a_soft_deleted_flow_stay_listed_with_the_flow_name(
    client: httpx.AsyncClient,
) -> None:
    flow = await create_flow(client)
    ran = await client.post(f"/flows/{flow['id']}/runs", json={"test": True, "input": {}})
    run_id = ran.json()["run_id"]
    before = (await client.get("/runs")).json()["items"][0]
    assert (before["flow_name"], before["flow_deleted"]) == ("Demo", False)

    await client.delete(f"/flows/{flow['id']}")

    (item,) = (await client.get("/runs")).json()["items"]
    assert (item["flow_name"], item["flow_deleted"]) == ("Demo", True)
    detail = (await client.get(f"/runs/{run_id}")).json()
    assert (detail["flow_name"], detail["flow_deleted"]) == ("Demo", True)


@pytest.mark.usefixtures("soft")
async def test_soft_delete_hides_the_versions_of_the_flow(client: httpx.AsyncClient) -> None:
    flow = await create_flow(client)
    await client.post(f"/flows/{flow['id']}/publish")
    await client.delete(f"/flows/{flow['id']}")
    assert (await client.get(f"/flows/{flow['id']}/versions")).status_code == 404
    assert (await client.get(f"/flows/{flow['id']}/versions/1")).status_code == 404


@pytest.mark.usefixtures("soft")
async def test_the_soft_window_marks_old_versions_instead_of_removing_them(
    client: httpx.AsyncClient, flow_store: FakeFlowStore
) -> None:
    app.dependency_overrides[get_limits] = lambda: Limits(_env_file=None, max_versions_per_flow=2)
    flow = await create_flow(client)
    await edit_and_publish(client, flow, 4)

    assert await version_numbers(client, flow) == ([4, 3], 2)
    assert (await client.get(f"/flows/{flow['id']}/versions/1")).status_code == 404
    assert len(flow_store.versions) == 4
    marked = [v for v in flow_store.versions if v.deleted_at is not None]
    assert sorted(v.version for v in marked) == [1, 2]
    assert all(v.deleted_by is not None for v in marked)
