import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.flows.models import Flow
from app.flows.store import get_store
from app.main import app
from app.runs.models import Run
from app.runs.router import get_observer_factory
from app.runs.store import get_run_store

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "flows"


class FakeFlowStore:
    def __init__(self) -> None:
        self.flows: dict[uuid.UUID, Flow] = {}

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


class FakeRunStore:
    def __init__(self) -> None:
        self.runs: dict[uuid.UUID, Run] = {}

    async def add_run(self, run: Run) -> Run:
        run.id = uuid.uuid4()
        self.runs[run.id] = run
        return run

    async def get_run(self, run_id: uuid.UUID) -> Run | None:
        return self.runs.get(run_id)


class StubObserver:
    """Records nothing; exposes a fixed trace id like MlflowObserver after a run starts."""

    trace_id: str | None = "tr-stub"

    async def run_started(self, inputs: dict[str, Any]) -> None: ...

    async def node_started(self, node: Any, inputs: dict[str, Any]) -> None: ...

    async def node_finished(self, *args: Any, **kwargs: Any) -> None: ...

    async def run_finished(self, *args: Any, **kwargs: Any) -> None: ...


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def flow_store() -> FakeFlowStore:
    return FakeFlowStore()


@pytest.fixture
def run_store() -> FakeRunStore:
    return FakeRunStore()


@pytest.fixture
async def client(flow_store: FakeFlowStore, run_store: FakeRunStore):
    app.dependency_overrides[get_store] = lambda: flow_store
    app.dependency_overrides[get_run_store] = lambda: run_store
    app.dependency_overrides[get_observer_factory] = lambda: lambda _name: StubObserver()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    for dep in (get_store, get_run_store, get_observer_factory):
        app.dependency_overrides.pop(dep, None)


def example(name: str) -> dict[str, Any]:
    return json.loads((EXAMPLES / name).read_text())


async def create_flow(client: httpx.AsyncClient, draft: dict[str, Any] | None = None) -> dict:
    body: dict[str, Any] = {"name": "Demo"}
    if draft is not None:
        body["draft"] = draft
    response = await client.post("/flows", json=body)
    assert response.status_code == 201
    return response.json()
