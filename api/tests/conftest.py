import copy
import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.auth.models import Principal
from app.catalog.health import HealthSource, get_health_source
from app.catalog.models import InstalledItem
from app.catalog.remote import CatalogSource, get_catalog_source
from app.catalog.store import ItemDraft, get_installed_store
from app.connections.models import Connection
from app.connections.store import NameTaken, get_connection_store
from app.connections.types import Bearer, ConnectionType, FieldSpec
from app.flows.models import Flow, FlowVersion
from app.flows.store import (
    AlreadyPublished,
    DraftMoved,
    FlowMissing,
    get_store,
)
from app.limits import Limits
from app.main import app
from app.ratelimit import RateLimiters
from app.runs.models import Run
from app.runs.router import get_observer_factory
from app.runs.store import FlowInfo, get_run_store
from app.secrets.models import Secret
from app.secrets.store import get_secret_store
from app.workspaces.deps import get_workspace_store
from app.workspaces.schemas import Member
from tests.auth_helpers import bearer
from tests.db_fixtures import postgres_url, sessions  # noqa: F401  (fixtures for -m db tests)

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "flows"
MARKETPLACE = Path(__file__).resolve().parents[2] / "marketplace"


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
        self.versions: list[FlowVersion] = []

    def _visible(self, member: Member, flow_id: uuid.UUID) -> Flow | None:
        flow = self.flows.get(flow_id)
        live = flow is not None and flow.deleted_at is None
        return flow if live and flow.workspace_id == member.workspace_id else None

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

    async def delete_flow(self, member: Member, flow_id: uuid.UUID, *, soft: bool) -> bool:
        flow = self._visible(member, flow_id)
        if flow is None:
            return False
        if soft:
            flow.deleted_at = datetime.now(UTC).replace(tzinfo=None)
            flow.deleted_by = member.user_id
        else:
            del self.flows[flow_id]
        return True

    async def count_flows(self, member: Member) -> int:
        return sum(
            f.workspace_id == member.workspace_id
            and f.created_by == member.user_id
            and f.deleted_at is None
            for f in self.flows.values()
        )

    async def list_flows(
        self, member: Member, q: str | None, sort: str, page: int, page_size: int
    ) -> tuple[list[Flow], int]:
        flows = [
            f
            for f in self.flows.values()
            if f.workspace_id == member.workspace_id
            and f.deleted_at is None
            and (not q or q.lower() in f.name.lower())
        ]
        start = (page - 1) * page_size
        return flows[start : start + page_size], len(flows)

    async def get_flow(self, member: Member, flow_id: uuid.UUID) -> Flow | None:
        return self._visible(member, flow_id)

    async def unpublish(self, member: Member, flow_id: uuid.UUID) -> Flow | None:
        flow = self._visible(member, flow_id)
        if flow is None or flow.published_version is None:
            return None
        flow.published_version = None
        flow.published_draft_version = None
        flow.published_at = None
        return flow

    async def list_callers(self, member: Member, flow_id: uuid.UUID) -> list[Flow]:
        found = []
        for flow in self.flows.values():
            if flow.id == flow_id or self._visible(member, flow.id) is None:
                continue
            version = next(
                (
                    v
                    for v in self.versions
                    if v.flow_id == flow.id
                    and v.version == flow.published_version
                    and v.deleted_at is None
                ),
                None,
            )
            nodes = version.graph.get("nodes", []) if version else []
            target = str(flow_id)
            if any(
                (n.get("type") == "subflow" and n.get("data", {}).get("flow_id") == target)
                or (
                    n.get("type") == "agent"
                    and any(t.get("flow_id") == target for t in n.get("data", {}).get("tools", []))
                )
                for n in nodes
            ):
                found.append(flow)
        return sorted(found, key=lambda f: (f.name, f.id))

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

    async def publish(
        self,
        member: Member,
        flow_id: uuid.UUID,
        expected_draft_version: int,
        keep_versions: int = 0,
        *,
        soft: bool,
    ) -> FlowVersion:
        flow = self._visible(member, flow_id)
        if flow is None:
            raise FlowMissing
        if flow.draft_version != expected_draft_version:
            raise DraftMoved
        if flow.published_draft_version == flow.draft_version:
            raise AlreadyPublished
        now = datetime.now(UTC).replace(tzinfo=None)
        version = FlowVersion(
            id=uuid.uuid4(),
            flow_id=flow.id,
            version=max((v.version for v in self.versions if v.flow_id == flow.id), default=0) + 1,
            graph=copy.deepcopy(flow.draft),
            source_draft_version=flow.draft_version,
            created_by=member.user_id,
            created_at=now,
        )
        self.versions.append(version)
        if keep_versions:
            old = [
                v
                for v in self.versions
                if v.flow_id == flow.id
                and v.deleted_at is None
                and v.version <= version.version - keep_versions
            ]
            for v in old:
                if soft:
                    v.deleted_at = now
                    v.deleted_by = member.user_id
                else:
                    self.versions.remove(v)
        flow.published_version = version.version
        flow.published_draft_version = flow.draft_version
        flow.published_at = now
        return version

    async def list_versions(self, member: Member, flow_id: uuid.UUID) -> list[FlowVersion]:
        if self._visible(member, flow_id) is None:
            return []
        found = [v for v in self.versions if v.flow_id == flow_id and v.deleted_at is None]
        return sorted(found, key=lambda v: v.version, reverse=True)

    async def get_version(
        self, member: Member, flow_id: uuid.UUID, version: int
    ) -> FlowVersion | None:
        return next(
            (v for v in await self.list_versions(member, flow_id) if v.version == version), None
        )


class FakeRunStore:
    def __init__(self, flows: "FakeFlowStore") -> None:
        self.runs: dict[uuid.UUID, Run] = {}
        self.flows = flows

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

    async def flow_infos(
        self, member: Member, flow_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, FlowInfo]:
        found = {
            i: f
            for i in flow_ids
            if (f := self.flows.flows.get(i)) is not None and f.workspace_id == member.workspace_id
        }
        return {
            i: FlowInfo(name=f.name, deleted=f.deleted_at is not None) for i, f in found.items()
        }


class FakeSecretStore:
    def __init__(self) -> None:
        self.secrets: dict[tuple[uuid.UUID, str], Secret] = {}

    async def list_secrets(self, member: Member) -> list[Secret]:
        rows = [s for (ws, _), s in self.secrets.items() if ws == member.workspace_id]
        return sorted(rows, key=lambda s: s.name)

    async def count(self, member: Member) -> int:
        return len(await self.list_secrets(member))

    async def exists(self, member: Member, name: str) -> bool:
        return (member.workspace_id, name) in self.secrets

    async def get_encrypted(self, member: Member, names: set[str]) -> dict[str, str]:
        found = {n: self.secrets.get((member.workspace_id, n)) for n in names}
        return {n: s.value_encrypted for n, s in found.items() if s is not None}

    async def put(self, member: Member, name: str, encrypted: str) -> Secret:
        now = datetime.now(UTC)
        key = (member.workspace_id, name)
        secret = self.secrets.get(key)
        if secret is None:
            secret = Secret(
                id=uuid.uuid4(),
                workspace_id=member.workspace_id,
                name=name,
                created_by=member.user_id,
                created_at=now,
            )
            self.secrets[key] = secret
        secret.value_encrypted = encrypted
        secret.updated_by = member.user_id
        secret.updated_at = now
        return secret

    async def delete(self, member: Member, name: str) -> bool:
        return self.secrets.pop((member.workspace_id, name), None) is not None


def service_type(**changes: Any) -> ConnectionType:
    """A made-up service with fixed hosts and a test call, like a catalog type would be."""
    base = ConnectionType(
        id="acme",
        name="Acme",
        description="An Acme API key, sent only to the Acme host.",
        fields=[FieldSpec(name="api_key", label="API key", secret=True)],
        auth=Bearer(token="api_key"),
        fixed_hosts=["127.0.0.1"],
        test_url="https://api.acme.test/v1/ping",
    )
    return base.model_copy(update=changes)


class FakeConnectionStore:
    def __init__(self, flows: "FakeFlowStore") -> None:
        self.flows = flows
        self.rows: dict[uuid.UUID, Connection] = {}

    def _mine(self, member: Member) -> list[Connection]:
        return [c for c in self.rows.values() if c.workspace_id == member.workspace_id]

    async def list_connections(self, member: Member) -> list[Connection]:
        return sorted(self._mine(member), key=lambda c: c.name)

    async def count(self, member: Member) -> int:
        return len(self._mine(member))

    async def count_by_type(self, member: Member, type_id: str) -> int:
        return sum(c.type == type_id for c in self._mine(member))

    async def get(self, member: Member, connection_id: uuid.UUID) -> Connection | None:
        found = self.rows.get(connection_id)
        return found if found and found.workspace_id == member.workspace_id else None

    async def get_many(self, member: Member, ids: set[uuid.UUID]) -> list[Connection]:
        return [c for c in self._mine(member) if c.id in ids]

    def _taken(self, member: Member, name: str, keep: uuid.UUID | None = None) -> bool:
        return any(c.name == name and c.id != keep for c in self._mine(member))

    async def add(
        self, member: Member, type_id: str, name: str, config: dict[str, Any], encrypted: str
    ) -> Connection:
        if self._taken(member, name):
            raise NameTaken
        now = datetime.now(UTC)
        connection = Connection(
            id=uuid.uuid4(),
            workspace_id=member.workspace_id,
            type=type_id,
            name=name,
            config=config,
            secrets_encrypted=encrypted,
            created_by=member.user_id,
            updated_by=member.user_id,
            created_at=now,
            updated_at=now,
        )
        self.rows[connection.id] = connection
        return connection

    async def replace(
        self,
        member: Member,
        connection_id: uuid.UUID,
        name: str,
        config: dict[str, Any],
        encrypted: str,
    ) -> Connection | None:
        connection = await self.get(member, connection_id)
        if connection is None:
            return None
        if self._taken(member, name, keep=connection_id):
            raise NameTaken
        connection.name, connection.config, connection.secrets_encrypted = name, config, encrypted
        connection.updated_at = datetime.now(UTC)
        return connection

    async def delete(self, member: Member, connection_id: uuid.UUID) -> bool:
        if await self.get(member, connection_id) is None:
            return False
        del self.rows[connection_id]
        return True

    async def flows_using(self, member: Member, connection_id: uuid.UUID) -> list[Flow]:
        wanted = str(connection_id)

        def uses(graph: dict[str, Any]) -> bool:
            return any(
                isinstance(n.get("data"), dict) and n["data"].get("connection_id") == wanted
                for n in graph.get("nodes", [])
            )

        found = []
        for flow in self.flows.flows.values():
            if flow.workspace_id != member.workspace_id or flow.deleted_at is not None:
                continue
            published = next(
                (
                    v.graph
                    for v in self.flows.versions
                    if v.flow_id == flow.id and v.version == flow.published_version
                ),
                {},
            )
            if uses(flow.draft) or uses(published):
                found.append(flow)
        return sorted(found, key=lambda f: (f.name, f.id))


class FakeInstalledStore:
    def __init__(self) -> None:
        self.rows: dict[tuple[uuid.UUID, str, str], InstalledItem] = {}

    async def list_items(self, member: Member, kind: str | None = None) -> list[InstalledItem]:
        rows = [
            r
            for (ws, k, _), r in self.rows.items()
            if ws == member.workspace_id and (kind is None or k == kind)
        ]
        return sorted(rows, key=lambda r: (r.kind, r.item_id))

    async def get(self, member: Member, kind: str, item_id: str) -> InstalledItem | None:
        return self.rows.get((member.workspace_id, kind, item_id))

    async def count(self, member: Member) -> int:
        return len(await self.list_items(member))

    async def put_all(self, member: Member, drafts: Sequence[ItemDraft]) -> list[InstalledItem]:
        items = [
            InstalledItem(
                id=uuid.uuid4(),
                workspace_id=member.workspace_id,
                kind=d.kind,
                item_id=d.item_id,
                version=d.version,
                hash=d.hash,
                definition=copy.deepcopy(d.definition),
                installed_by=member.user_id,
                installed_at=datetime.now(UTC),
            )
            for d in drafts
        ]
        for item in items:
            self.rows[(member.workspace_id, item.kind, item.item_id)] = item
        return items

    async def delete(self, member: Member, kind: str, item_id: str) -> bool:
        return self.rows.pop((member.workspace_id, kind, item_id), None) is not None


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
def run_store(flow_store: FakeFlowStore) -> FakeRunStore:
    return FakeRunStore(flow_store)


@pytest.fixture
def secret_store() -> FakeSecretStore:
    return FakeSecretStore()


@pytest.fixture
def installed_store() -> FakeInstalledStore:
    return FakeInstalledStore()


@pytest.fixture
def catalog_source() -> CatalogSource:
    return CatalogSource(str(MARKETPLACE))


@pytest.fixture
def health_source() -> HealthSource:
    return HealthSource("")


@pytest.fixture
def connection_store(flow_store: FakeFlowStore) -> FakeConnectionStore:
    return FakeConnectionStore(flow_store)


@pytest.fixture
def workspace_store() -> FakeWorkspaceStore:
    return FakeWorkspaceStore()


@pytest.fixture
async def client(
    flow_store: FakeFlowStore,
    run_store: FakeRunStore,
    workspace_store: FakeWorkspaceStore,
    secret_store: FakeSecretStore,
    connection_store: FakeConnectionStore,
    installed_store: FakeInstalledStore,
    catalog_source: CatalogSource,
    health_source: HealthSource,
):
    app.dependency_overrides[get_store] = lambda: flow_store
    app.dependency_overrides[get_secret_store] = lambda: secret_store
    app.dependency_overrides[get_connection_store] = lambda: connection_store
    app.dependency_overrides[get_installed_store] = lambda: installed_store
    app.dependency_overrides[get_catalog_source] = lambda: catalog_source
    app.dependency_overrides[get_health_source] = lambda: health_source
    app.dependency_overrides[get_run_store] = lambda: run_store
    app.dependency_overrides[get_workspace_store] = lambda: workspace_store
    app.dependency_overrides[get_observer_factory] = lambda: lambda _name: StubObserver()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers=bearer()
    ) as c:
        yield c
    for dep in (
        get_store,
        get_secret_store,
        get_connection_store,
        get_installed_store,
        get_catalog_source,
        get_health_source,
        get_run_store,
        get_workspace_store,
        get_observer_factory,
    ):
        app.dependency_overrides.pop(dep, None)


@pytest.fixture
async def anon_client(
    flow_store: FakeFlowStore,
    run_store: FakeRunStore,
    workspace_store: FakeWorkspaceStore,
    secret_store: FakeSecretStore,
    connection_store: FakeConnectionStore,
    installed_store: FakeInstalledStore,
    catalog_source: CatalogSource,
    health_source: HealthSource,
):
    app.dependency_overrides[get_store] = lambda: flow_store
    app.dependency_overrides[get_secret_store] = lambda: secret_store
    app.dependency_overrides[get_connection_store] = lambda: connection_store
    app.dependency_overrides[get_installed_store] = lambda: installed_store
    app.dependency_overrides[get_catalog_source] = lambda: catalog_source
    app.dependency_overrides[get_health_source] = lambda: health_source
    app.dependency_overrides[get_run_store] = lambda: run_store
    app.dependency_overrides[get_workspace_store] = lambda: workspace_store
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    for dep in (
        get_store,
        get_secret_store,
        get_connection_store,
        get_installed_store,
        get_catalog_source,
        get_health_source,
        get_run_store,
        get_workspace_store,
    ):
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
