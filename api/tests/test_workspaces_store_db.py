import asyncio

import pytest
from sqlalchemy import delete, func, select

from app.auth.models import Principal
from app.flows.models import Flow
from app.flows.store import FlowStore
from app.runs.models import Run
from app.runs.store import RunStore
from app.workspaces.models import User, Workspace, WorkspaceMember
from app.workspaces.store import WorkspaceStore, workspace_name
from tests.db_fixtures import SessionFactory, anyio_backend, make_member  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.anyio]


def principal(sub: str = "user-1", **overrides) -> Principal:
    fields = dict(sub=sub, provider="web", email=f"{sub}@example.com", name="Ada")
    return Principal(**{**fields, **overrides})


async def counts(sessions: SessionFactory) -> tuple[int, int, int]:
    async with sessions() as session:
        users = await session.scalar(select(func.count()).select_from(User))
        workspaces = await session.scalar(select(func.count()).select_from(Workspace))
        members = await session.scalar(select(func.count()).select_from(WorkspaceMember))
    return users or 0, workspaces or 0, members or 0


async def test_the_first_request_creates_a_user_a_workspace_and_an_owner_membership(
    sessions: SessionFactory,
) -> None:
    async with sessions() as session:
        member = await WorkspaceStore(session).ensure_member(principal())
    assert await counts(sessions) == (1, 1, 1)
    async with sessions() as session:
        row = (
            await session.execute(
                select(Workspace.name, WorkspaceMember.role).join(
                    WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id
                )
            )
        ).one()
    assert (row.name, row.role) == ("Ada's workspace", "owner")
    assert member.user_id and member.workspace_id


async def test_later_requests_reuse_the_same_member(sessions: SessionFactory) -> None:
    first = await make_member(sessions)
    second = await make_member(sessions)
    assert first == second
    assert await counts(sessions) == (1, 1, 1)


async def test_different_people_get_separate_workspaces(sessions: SessionFactory) -> None:
    a, b = await make_member(sessions, "a"), await make_member(sessions, "b")
    assert a.workspace_id != b.workspace_id and a.user_id != b.user_id
    assert await counts(sessions) == (2, 2, 2)


async def test_the_same_sub_from_another_provider_is_another_user(
    sessions: SessionFactory,
) -> None:
    async with sessions() as session:
        store = WorkspaceStore(session)
        web = await store.ensure_member(principal(provider="web"))
        github = await store.ensure_member(principal(provider="github"))
    assert web.user_id != github.user_id


async def test_simultaneous_first_requests_still_make_one_workspace(
    sessions: SessionFactory,
) -> None:
    async def first_request() -> object:
        async with sessions() as session:
            return await WorkspaceStore(session).ensure_member(principal())

    members = await asyncio.gather(*(first_request() for _ in range(5)))
    assert len(set(members)) == 1
    assert await counts(sessions) == (1, 1, 1)


async def test_deleting_a_workspace_removes_its_flows_and_runs(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    async with sessions() as session:
        flow = await FlowStore(session).create_flow(member, "Demo", {})
        await RunStore(session).add_run(
            Run(
                flow_id=flow.id,
                workspace_id=member.workspace_id,
                created_by=member.user_id,
                status="succeeded",
                test=True,
                input={},
                output={},
                error=None,
                duration_ms=1,
            )
        )
        await session.execute(delete(Workspace).where(Workspace.id == member.workspace_id))
        await session.commit()
        assert await session.scalar(select(func.count()).select_from(Flow)) == 0
        assert await session.scalar(select(func.count()).select_from(Run)) == 0


def test_a_long_name_keeps_the_workspace_suffix() -> None:
    assert workspace_name(principal(name="x" * 300)).endswith("'s workspace")
    assert len(workspace_name(principal(name="x" * 300))) <= 120


def test_the_workspace_name_falls_back_from_name_to_email_to_a_default() -> None:
    assert workspace_name(principal(name="Ada")) == "Ada's workspace"
    assert workspace_name(principal(name=None, email="grace@example.com")) == "grace's workspace"
    assert workspace_name(principal(name=None, email=None)) == "My workspace"
