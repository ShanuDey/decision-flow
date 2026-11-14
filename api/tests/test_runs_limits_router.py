import asyncio
import uuid
from collections.abc import Iterator

import httpx
import pytest

from app.limits import Limits, get_limits
from app.main import app
from app.runs.router import get_observer_factory
from app.runs.slots import RunSlots, get_run_slots
from tests.conftest import FakeRunStore, FakeWorkspaceStore, StubObserver, create_flow

pytestmark = pytest.mark.anyio

RUN = {"test": True, "input": {}}


def limits(**fields: int) -> Limits:
    return Limits(_env_file=None, **fields)


@pytest.fixture
def overrides() -> Iterator[None]:
    yield
    for dep in (get_run_slots, get_limits, get_observer_factory):
        app.dependency_overrides.pop(dep, None)


@pytest.mark.usefixtures("overrides")
async def test_a_full_app_refuses_the_run_with_retry_after_and_stores_nothing(
    client: httpx.AsyncClient, run_store: FakeRunStore
) -> None:
    slots = RunSlots(limits(max_concurrent_runs=1))
    app.dependency_overrides[get_run_slots] = lambda: slots
    flow = await create_flow(client)

    async with slots.hold(uuid.uuid4()):
        refused = await client.post(f"/flows/{flow['id']}/runs", json=RUN)
    assert refused.status_code == 429
    assert refused.headers["retry-after"] == "5"
    assert refused.json()["code"] == "run_limit"
    assert refused.json()["details"]["scope"] == "app"
    assert run_store.runs == {}

    assert (await client.post(f"/flows/{flow['id']}/runs", json=RUN)).status_code == 200


@pytest.mark.usefixtures("overrides")
async def test_a_busy_workspace_is_refused_but_the_app_still_has_room(
    client: httpx.AsyncClient, workspace_store: FakeWorkspaceStore
) -> None:
    slots = RunSlots(limits(max_concurrent_runs_per_workspace=1))
    app.dependency_overrides[get_run_slots] = lambda: slots
    flow = await create_flow(client)
    (member,) = workspace_store.members.values()

    async with slots.hold(member.workspace_id):
        refused = await client.post(f"/flows/{flow['id']}/runs", json=RUN)
    assert refused.status_code == 429
    assert refused.json()["details"]["scope"] == "workspace"


@pytest.mark.usefixtures("overrides")
async def test_bad_requests_do_not_need_a_slot(client: httpx.AsyncClient) -> None:
    slots = RunSlots(limits(max_concurrent_runs=1))
    app.dependency_overrides[get_run_slots] = lambda: slots
    flow = await create_flow(client)

    async with slots.hold(uuid.uuid4()):
        missing = await client.post(f"/flows/{uuid.uuid4()}/runs", json=RUN)
        unpublished = await client.post(f"/flows/{flow['id']}/runs", json={"input": {}})
    assert missing.status_code == 404
    assert unpublished.status_code == 422


@pytest.mark.usefixtures("overrides")
async def test_runs_free_their_slot_when_they_finish(client: httpx.AsyncClient) -> None:
    slots = RunSlots(limits(max_concurrent_runs=1))
    app.dependency_overrides[get_run_slots] = lambda: slots
    flow = await create_flow(client)

    for _ in range(3):
        assert (await client.post(f"/flows/{flow['id']}/runs", json=RUN)).status_code == 200
    assert slots.running == 0


class SlowObserver(StubObserver):
    async def node_started(self, *args: object, **kwargs: object) -> None:
        await asyncio.sleep(30)


@pytest.mark.usefixtures("overrides")
async def test_a_run_over_the_timeout_is_recorded_as_failed(
    client: httpx.AsyncClient, run_store: FakeRunStore
) -> None:
    app.dependency_overrides[get_limits] = lambda: limits(run_timeout_seconds=1)
    app.dependency_overrides[get_observer_factory] = lambda: lambda _name: SlowObserver()
    flow = await create_flow(client)

    response = await client.post(f"/flows/{flow['id']}/runs", json=RUN)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error"]["message"] == "Run timed out after 1 seconds"
    assert len(run_store.runs) == 1
