import asyncio
import uuid

import pytest

from app.flows.store import FlowStore
from app.workspaces.schemas import Member
from tests.db_fixtures import SessionFactory, anyio_backend, make_member  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.anyio]


async def make(sessions: SessionFactory, member: Member, *names: str) -> list:
    async with sessions() as session:
        store = FlowStore(session)
        return [await store.create_flow(member, name, {"name": name}) for name in names]


async def test_create_then_get_from_another_session(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    (flow,) = await make(sessions, member, "Demo")
    assert flow.draft_version == 1 and flow.created_at and flow.updated_at
    assert (flow.workspace_id, flow.created_by, flow.updated_by) == (
        member.workspace_id,
        member.user_id,
        member.user_id,
    )

    async with sessions() as other:
        loaded = await FlowStore(other).get_flow(member, flow.id)
    assert loaded is not None
    assert (loaded.name, loaded.draft) == ("Demo", {"name": "Demo"})


async def test_get_missing_flow_is_none(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    async with sessions() as session:
        assert await FlowStore(session).get_flow(member, uuid.uuid4()) is None


async def test_search_treats_percent_and_underscore_literally(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    await make(sessions, member, "100% sure", "1000 sure", "a_b", "axb", "Alpha")
    async with sessions() as session:
        store = FlowStore(session)
        names = lambda rows: sorted(f.name for f in rows[0])  # noqa: E731
        assert names(await store.list_flows(member, "%", "name", 1, 25)) == ["100% sure"]
        assert names(await store.list_flows(member, "_", "name", 1, 25)) == ["a_b"]
        assert names(await store.list_flows(member, "ALPHA", "name", 1, 25)) == [
            "Alpha"
        ]  # case-insensitive
        assert (await store.list_flows(member, "nothing", "name", 1, 25))[1] == 0


async def test_sort_and_paging_report_the_total(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    await make(sessions, member, "c", "a", "e", "b", "d")
    async with sessions() as session:
        store = FlowStore(session)
        page1, total = await store.list_flows(member, None, "name", 1, 2)
        page2, _ = await store.list_flows(member, None, "name", 2, 2)
        page3, _ = await store.list_flows(member, None, "name", 3, 2)
        newest_last, _ = await store.list_flows(member, None, "-name", 1, 5)
    assert total == 5
    assert [f.name for f in page1] == ["a", "b"]
    assert [f.name for f in page2] == ["c", "d"]
    assert [f.name for f in page3] == ["e"]
    assert [f.name for f in newest_last] == ["e", "d", "c", "b", "a"]


async def test_save_draft_bumps_the_version_and_stores_the_draft(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    (flow,) = await make(sessions, member, "Demo")
    async with sessions() as session:
        saved = await FlowStore(session).save_draft(member, flow.id, {"changed": True}, 1)
    assert saved is not None and saved.draft_version == 2
    assert saved.updated_at >= flow.updated_at

    async with sessions() as other:
        loaded = await FlowStore(other).get_flow(member, flow.id)
    assert loaded is not None
    assert (loaded.draft, loaded.draft_version) == ({"changed": True}, 2)


async def test_rename_keeps_the_draft_and_version(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    (flow,) = await make(sessions, member, "Demo")
    async with sessions() as session:
        renamed = await FlowStore(session).rename_flow(member, flow.id, "Other")
    assert renamed is not None and renamed.updated_at >= flow.updated_at

    async with sessions() as other:
        loaded = await FlowStore(other).get_flow(member, flow.id)
    assert loaded is not None
    assert (loaded.name, loaded.draft, loaded.draft_version) == ("Other", {"name": "Demo"}, 1)


async def test_renaming_a_missing_flow_is_none(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    async with sessions() as session:
        assert await FlowStore(session).rename_flow(member, uuid.uuid4(), "x") is None


async def test_a_stale_version_changes_nothing(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    (flow,) = await make(sessions, member, "Demo")
    async with sessions() as session:
        store = FlowStore(session)
        assert await store.save_draft(member, flow.id, {"v": 2}, 1) is not None
        assert await store.save_draft(member, flow.id, {"v": "stale"}, 1) is None
    async with sessions() as other:
        loaded = await FlowStore(other).get_flow(member, flow.id)
    assert loaded is not None and loaded.draft == {"v": 2}


async def test_saving_a_missing_flow_is_none(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    async with sessions() as session:
        assert await FlowStore(session).save_draft(member, uuid.uuid4(), {}, 1) is None


async def test_concurrent_saves_with_the_same_version_have_one_winner(
    sessions: SessionFactory,
) -> None:
    member = await make_member(sessions)
    (flow,) = await make(sessions, member, "Demo")

    async def save(draft: dict) -> object:
        async with sessions() as session:
            return await FlowStore(session).save_draft(member, flow.id, draft, 1)

    results = await asyncio.gather(*(save({"writer": n}) for n in range(5)))
    winners = [r for r in results if r is not None]
    assert len(winners) == 1

    async with sessions() as other:
        loaded = await FlowStore(other).get_flow(member, flow.id)
    assert loaded is not None and loaded.draft_version == 2
    assert loaded.draft == winners[0].draft


async def test_another_workspace_sees_and_changes_nothing(sessions: SessionFactory) -> None:
    owner, outsider = await make_member(sessions, "a"), await make_member(sessions, "b")
    (flow,) = await make(sessions, owner, "Demo")
    async with sessions() as session:
        store = FlowStore(session)
        assert await store.get_flow(outsider, flow.id) is None
        assert await store.list_flows(outsider, None, "name", 1, 25) == ([], 0)
        assert await store.rename_flow(outsider, flow.id, "Hijacked") is None
        assert await store.save_draft(outsider, flow.id, {"x": 1}, 1) is None
    async with sessions() as other:
        loaded = await FlowStore(other).get_flow(owner, flow.id)
    assert loaded is not None
    assert (loaded.name, loaded.draft, loaded.draft_version) == ("Demo", {"name": "Demo"}, 1)


async def test_count_flows_counts_only_the_members_own(sessions: SessionFactory) -> None:
    mine = await make_member(sessions)
    other = await make_member(sessions, "user-2")
    await make(sessions, mine, "A", "B")
    await make(sessions, other, "C")
    async with sessions() as session:
        store = FlowStore(session)
        assert await store.count_flows(mine) == 2
        assert await store.count_flows(other) == 1


async def test_delete_flow_is_scoped_to_the_workspace(sessions: SessionFactory) -> None:
    mine = await make_member(sessions)
    other = await make_member(sessions, "user-2")
    (flow,) = await make(sessions, mine, "A")
    async with sessions() as session:
        store = FlowStore(session)
        assert await store.delete_flow(other, flow.id) is False
        assert await store.get_flow(mine, flow.id) is not None
        assert await store.delete_flow(mine, flow.id) is True
        assert await store.delete_flow(mine, flow.id) is False
