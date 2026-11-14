import uuid
from collections.abc import Iterator

import httpx
import pytest

from app.limits import Limits, get_limits
from app.main import app
from app.runs.store import FlowGone
from tests.conftest import FakeRunStore, create_flow

pytestmark = pytest.mark.anyio


@pytest.fixture
def override() -> Iterator[None]:
    yield
    app.dependency_overrides.pop(get_limits, None)


async def test_delete_removes_the_flow_then_404s(client: httpx.AsyncClient) -> None:
    flow = await create_flow(client)

    assert (await client.delete(f"/flows/{flow['id']}")).status_code == 204
    assert (await client.get(f"/flows/{flow['id']}")).status_code == 404
    again = await client.delete(f"/flows/{flow['id']}")
    assert again.status_code == 404
    assert again.json()["code"] == "not_found"
    assert (await client.get("/flows")).json()["total"] == 0


async def test_deleting_an_unknown_flow_is_404(client: httpx.AsyncClient) -> None:
    assert (await client.delete(f"/flows/{uuid.uuid4()}")).status_code == 404


@pytest.mark.usefixtures("override")
async def test_deleting_a_flow_frees_a_slot_under_the_cap(client: httpx.AsyncClient) -> None:
    app.dependency_overrides[get_limits] = lambda: Limits(_env_file=None, max_flows_per_user=1)
    flow = await create_flow(client)
    assert (await client.post("/flows", json={"name": "Two"})).status_code == 409

    assert (await client.delete(f"/flows/{flow['id']}")).status_code == 204
    assert (await client.post("/flows", json={"name": "Two"})).status_code == 201


async def test_a_flow_deleted_mid_run_is_a_404_not_a_500(
    client: httpx.AsyncClient, run_store: FakeRunStore
) -> None:
    flow = await create_flow(client)

    async def gone(run: object) -> None:
        raise FlowGone

    run_store.add_run = gone  # type: ignore[method-assign]
    response = await client.post(f"/flows/{flow['id']}/runs", json={"test": True, "input": {}})
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
