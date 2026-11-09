import copy
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.flows.models import Flow, Run
from app.flows.store import get_store
from app.main import app

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "flows"


class FakeStore:
    def __init__(self) -> None:
        self.flows: dict[uuid.UUID, Flow] = {}
        self.runs: dict[uuid.UUID, Run] = {}

    async def create_flow(self, name: str, draft: dict[str, Any]) -> Flow:
        now = datetime.now(UTC)
        flow = Flow(
            id=uuid.uuid4(),
            name=name,
            draft=draft,
            draft_version=1,
            created_at=now,
            updated_at=now,
        )
        self.flows[flow.id] = flow
        return flow

    async def list_flows(
        self, q: str | None, sort: str, page: int, page_size: int
    ) -> tuple[list[Flow], int]:
        flows = [f for f in self.flows.values() if not q or q.lower() in f.name.lower()]
        start = (page - 1) * page_size
        return flows[start : start + page_size], len(flows)

    async def get_flow(self, flow_id: uuid.UUID) -> Flow | None:
        return self.flows.get(flow_id)

    async def save_draft(
        self, flow_id: uuid.UUID, draft: dict[str, Any], expected_version: int
    ) -> Flow | None:
        flow = self.flows.get(flow_id)
        if flow is None or flow.draft_version != expected_version:
            return None
        flow.draft = draft
        flow.draft_version += 1
        return flow

    async def add_run(self, run: Run) -> Run:
        run.id = uuid.uuid4()
        self.runs[run.id] = run
        return run

    async def get_run(self, run_id: uuid.UUID) -> Run | None:
        return self.runs.get(run_id)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
async def client(store: FakeStore):
    app.dependency_overrides[get_store] = lambda: store
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_store, None)


def example(name: str) -> dict[str, Any]:
    return json.loads((EXAMPLES / name).read_text())


async def create(client: httpx.AsyncClient, draft: dict[str, Any] | None = None) -> dict:
    body: dict[str, Any] = {"name": "Demo"}
    if draft is not None:
        body["draft"] = draft
    response = await client.post("/flows", json=body)
    assert response.status_code == 201
    return response.json()


@pytest.mark.anyio
async def test_create_without_draft_gives_a_valid_blank_flow(client: httpx.AsyncClient) -> None:
    flow = await create(client)
    assert flow["draft_version"] == 1
    assert (await client.post(f"/flows/{flow['id']}/validate")).json() == {"valid": True}


@pytest.mark.anyio
async def test_list_and_get(client: httpx.AsyncClient) -> None:
    flow = await create(client)
    listed = (await client.get("/flows", params={"q": "dem"})).json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == flow["id"]
    assert "draft" not in listed["items"][0]
    assert (await client.get(f"/flows/{flow['id']}")).json()["draft"] == flow["draft"]
    missing = await client.get(f"/flows/{uuid.uuid4()}")
    assert missing.status_code == 404 and missing.json()["code"] == "not_found"


@pytest.mark.anyio
async def test_save_draft_bumps_version_and_rejects_stale(client: httpx.AsyncClient) -> None:
    flow = await create(client)
    url = f"/flows/{flow['id']}/draft"
    saved = await client.put(url, json=example("start-end.json"), headers={"If-Match": "1"})
    assert saved.status_code == 200 and saved.json() == {"draft_version": 2}
    stale = await client.put(url, json=example("start-end.json"), headers={"If-Match": "1"})
    assert stale.status_code == 409
    assert stale.json()["code"] == "draft_conflict"
    assert stale.json()["details"] == {"draft_version": 2}


@pytest.mark.anyio
async def test_save_draft_requires_if_match(client: httpx.AsyncClient) -> None:
    flow = await create(client)
    response = await client.put(f"/flows/{flow['id']}/draft", json={})
    assert response.status_code == 428


@pytest.mark.anyio
async def test_save_draft_on_missing_flow_is_404(client: httpx.AsyncClient) -> None:
    response = await client.put(f"/flows/{uuid.uuid4()}/draft", json={}, headers={"If-Match": "1"})
    assert response.status_code == 404


@pytest.mark.anyio
async def test_an_invalid_draft_is_saved_but_fails_validation(client: httpx.AsyncClient) -> None:
    flow = await create(client)
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


@pytest.mark.anyio
async def test_test_run_returns_the_output(client: httpx.AsyncClient) -> None:
    flow = await create(client, example("assign-variable.json"))
    response = await client.post(
        f"/flows/{flow['id']}/runs?wait=true", json={"test": True, "input": {"amount": 5}}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["output"] == {"total": 5, "label": "Order total 5"}
    fetched = await client.get(f"/runs/{body['run_id']}")
    assert fetched.json() == body


@pytest.mark.anyio
async def test_bad_input_is_422_naming_the_field_and_creates_no_run(
    client: httpx.AsyncClient, store: FakeStore
) -> None:
    flow = await create(client, example("assign-variable.json"))
    response = await client.post(
        f"/flows/{flow['id']}/runs", json={"test": True, "input": {"amount": "5"}}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"
    assert response.json()["details"]["field"] == "amount"
    assert store.runs == {}


@pytest.mark.anyio
async def test_running_an_invalid_flow_is_422(client: httpx.AsyncClient, store: FakeStore) -> None:
    broken = copy.deepcopy(example("start-end.json"))
    broken["edges"] = []
    flow = await create(client, broken)
    response = await client.post(f"/flows/{flow['id']}/runs", json={"test": True})
    assert response.status_code == 422 and response.json()["code"] == "invalid_flow"
    assert store.runs == {}


@pytest.mark.anyio
async def test_a_non_test_run_is_refused_until_publish_exists(client: httpx.AsyncClient) -> None:
    flow = await create(client)
    response = await client.post(f"/flows/{flow['id']}/runs", json={"input": {}})
    assert response.status_code == 422 and response.json()["code"] == "not_published"


@pytest.mark.anyio
async def test_unknown_run_is_404(client: httpx.AsyncClient) -> None:
    assert (await client.get(f"/runs/{uuid.uuid4()}")).status_code == 404
