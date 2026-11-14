import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.auth.models import Principal
from app.flows.models import Flow
from app.flows.store import get_store
from app.limits import Limits
from app.main import app
from app.ratelimit import RateLimiters
from app.runs.models import Run
from app.runs.router import get_observer_factory
from app.runs.store import get_run_store
from app.workspaces.deps import get_workspace_store
from app.workspaces.schemas import Member
from tests.auth_helpers import bearer
from tests.db_fixtures import postgres_url, sessions  # noqa: F401  (fixtures for -m db tests)

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "flows"


class FakeWorkspaceStore:
    def __init__(self) -> None:
        self.members: dict[tuple[str, str], Member] = {}
        self.touched: list[uuid.UUID] = []

    async def touch(self, user_id: uuid.UUID) -> None:
        self.touched.append(user_id)

    async def find_member(self, principal: Principal) -> Member | None:
        return self.members.get((principal.provider, principal.sub))

    async def create_member(self, principal: Principal) -> tuple[Member, bool]:
        key = (principal.provider, principal.sub)
        created = key not in self.members
        if created:
            self.members[key] = Member(user_id=uuid.uuid4(), workspace_id=uuid.uuid4())
        return self.members[key], created

    async def ensure_member(self, principal: Principal) -> Member:
        return (await self.create_member(principal))[0]


class FakeFlowStore:
    def __init__(self) -> None:
        self.flows: dict[uuid.UUID, Flow] = {}

    def _visible(self, member: Member, flow_id: uuid.UUID) -> Flow | None:
        flow = self.flows.get(flow_id)
        return flow if flow is not None and flow.workspace_id == member.workspace_id else None

    async def create_flow(self, member: Member, name: str, draft: dict[str, Any]) -> Flow:
        now = datetime.now(UTC)
        flow = Flow(
            id=uuid.uuid4(),
            workspace_id=member.workspace_id,
            created_by=member.user_id,
            updated_by=member.user_id,
            name=name,
            draft=draft,
            draft_version=1,
            created_at=now,
            updated_at=now,
        )
        self.flows[flow.id] = flow
        return flow

    async def delete_flow(self, member: Member, flow_id: uuid.UUID) -> bool:
        return self._visible(member, flow_id) is not None and self.flows.pop(flow_id) is not None

    async def count_flows(self, member: Member) -> int:
        return sum(
            f.workspace_id == member.workspace_id and f.created_by == member.user_id
            for f in self.flows.values()
        )

    async def list_flows(
        self, member: Member, q: str | None, sort: str, page: int, page_size: int
    ) -> tuple[list[Flow], int]:
        flows = [
            f
            for f in self.flows.values()
            if f.workspace_id == member.workspace_id and (not q or q.lower() in f.name.lower())
        ]
        start = (page - 1) * page_size
        return flows[start : start + page_size], len(flows)

    async def get_flow(self, member: Member, flow_id: uuid.UUID) -> Flow | None:
        return self._visible(member, flow_id)

    async def rename_flow(self, member: Member, flow_id: uuid.UUID, name: str) -> Flow | None:
        flow = self._visible(member, flow_id)
        if flow is not None:
            flow.name = name
            flow.updated_by = member.user_id
            flow.updated_at = datetime.now(UTC)
        return flow

    async def save_draft(
        self, member: Member, flow_id: uuid.UUID, draft: dict[str, Any], expected_version: int
    ) -> Flow | None:
        flow = self._visible(member, flow_id)
        if flow is None or flow.draft_version != expected_version:
            return None
        flow.draft = draft
        flow.draft_version += 1
        flow.updated_by = member.user_id
        return flow


class FakeRunStore:
    def __init__(self) -> None:
        self.runs: dict[uuid.UUID, Run] = {}

    async def add_run(self, run: Run) -> Run:
        run.id = uuid.uuid4()
        run.started_at = datetime.now(UTC).replace(tzinfo=None)  # the column is timezone-naive
        self.runs[run.id] = run
        return run

    async def list_runs(
        self,
        member: Member,
        flow_id: uuid.UUID | None,
        status: str | None,
        test: bool | None,
        started_from: datetime | None,
        started_to: datetime | None,
        after: tuple[datetime, uuid.UUID] | None,
        limit: int,
    ) -> list[Run]:
        rows = sorted(self.runs.values(), key=lambda r: (r.started_at, r.id), reverse=True)
        keep = [
            r
            for r in rows
            if r.workspace_id == member.workspace_id
            and (flow_id is None or r.flow_id == flow_id)
            and (status is None or r.status == status)
            and (test is None or r.test == test)
            and (started_from is None or r.started_at >= started_from)
            and (started_to is None or r.started_at <= started_to)
            and (after is None or (r.started_at, r.id) < after)
        ]
        return keep[:limit]

    async def get_run(self, member: Member, run_id: uuid.UUID) -> Run | None:
        run = self.runs.get(run_id)
        return run if run is not None and run.workspace_id == member.workspace_id else None


class StubObserver:
    """Records nothing; exposes a fixed trace id like MlflowObserver after a run starts."""

    trace_id: str | None = "tr-stub"

    async def run_started(self, inputs: dict[str, Any]) -> None: ...

    async def node_started(self, node: Any, inputs: dict[str, Any]) -> None: ...

    async def node_finished(self, *args: Any, **kwargs: Any) -> None: ...

    async def run_finished(self, *args: Any, **kwargs: Any) -> None: ...


RATE_LIMIT_FIELDS = [name for name in Limits.model_fields if name.startswith("rate_limit_")]


@pytest.fixture(autouse=True)
def _rate_limits_off() -> None:
    off = {name: 0 for name in RATE_LIMIT_FIELDS}
    app.state.rate_limiters = RateLimiters(Limits(_env_file=None, **off))


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
def workspace_store() -> FakeWorkspaceStore:
    return FakeWorkspaceStore()


@pytest.fixture
async def client(
    flow_store: FakeFlowStore, run_store: FakeRunStore, workspace_store: FakeWorkspaceStore
):
    app.dependency_overrides[get_store] = lambda: flow_store
    app.dependency_overrides[get_run_store] = lambda: run_store
    app.dependency_overrides[get_workspace_store] = lambda: workspace_store
    app.dependency_overrides[get_observer_factory] = lambda: lambda _name: StubObserver()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers=bearer()
    ) as c:
        yield c
    for dep in (get_store, get_run_store, get_workspace_store, get_observer_factory):
        app.dependency_overrides.pop(dep, None)


@pytest.fixture
async def anon_client(
    flow_store: FakeFlowStore, run_store: FakeRunStore, workspace_store: FakeWorkspaceStore
):
    app.dependency_overrides[get_store] = lambda: flow_store
    app.dependency_overrides[get_run_store] = lambda: run_store
    app.dependency_overrides[get_workspace_store] = lambda: workspace_store
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    for dep in (get_store, get_run_store, get_workspace_store):
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
