import pytest

from app.connections.store import ConnectionStore, NameTaken
from app.flows.store import FlowStore
from app.workspaces.schemas import Member
from tests.db_fixtures import SessionFactory, anyio_backend, make_member  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.anyio]


async def add(sessions: SessionFactory, member: Member, name: str = "Billing"):
    async with sessions() as session:
        return await ConnectionStore(session).add(member, "bearer", name, {"hosts": "a.com"}, "enc")


async def test_add_then_read_from_another_session(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    made = await add(sessions, member)
    async with sessions() as session:
        loaded = await ConnectionStore(session).get(member, made.id)
        listed = await ConnectionStore(session).list_connections(member)
    assert loaded is not None and loaded.config == {"hosts": "a.com"}
    assert [c.id for c in listed] == [made.id]


async def test_a_name_is_unique_per_workspace(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    other = await make_member(sessions, "user-2")
    await add(sessions, member)
    with pytest.raises(NameTaken):
        await add(sessions, member)
    await add(sessions, other)


async def test_renaming_onto_a_taken_name_is_refused(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    await add(sessions, member, "One")
    two = await add(sessions, member, "Two")
    async with sessions() as session:
        with pytest.raises(NameTaken):
            await ConnectionStore(session).replace(member, two.id, "One", {}, "enc")


async def test_another_workspace_sees_and_changes_nothing(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    other = await make_member(sessions, "user-2")
    made = await add(sessions, member)
    async with sessions() as session:
        store = ConnectionStore(session)
        assert await store.get(other, made.id) is None
        assert await store.get_many(other, {made.id}) == []
        assert await store.replace(other, made.id, "x", {}, "enc") is None
        assert await store.delete(other, made.id) is False
    async with sessions() as session:
        assert await ConnectionStore(session).get(member, made.id) is not None


def graph_using(connection_id: str) -> dict:
    return {
        "nodes": [{"id": "n", "type": "http_request", "data": {"connection_id": connection_id}}]
    }


async def test_flows_using_finds_a_draft_or_the_latest_published_version(
    sessions: SessionFactory,
) -> None:
    member = await make_member(sessions)
    made = await add(sessions, member)
    wanted = str(made.id)
    async with sessions() as session:
        flows = FlowStore(session)
        in_draft = await flows.create_flow(member, "In draft", graph_using(wanted))
        unrelated = await flows.create_flow(member, "Unrelated", graph_using("other"))
        published = await flows.create_flow(member, "Published", graph_using(wanted))
    async with sessions() as session:
        await FlowStore(session).publish(member, published.id, 1, soft=False)
    async with sessions() as session:
        await FlowStore(session).save_draft(member, published.id, {"nodes": []}, 1)
    async with sessions() as session:
        found = await ConnectionStore(session).flows_using(member, made.id)
    names = [f.name for f in found]
    assert names == ["In draft", "Published"]
    assert unrelated.id not in [f.id for f in found] and in_draft.id in [f.id for f in found]


async def test_flows_using_ignores_other_workspaces_and_deleted_flows(
    sessions: SessionFactory,
) -> None:
    member = await make_member(sessions)
    other = await make_member(sessions, "user-2")
    made = await add(sessions, member)
    async with sessions() as session:
        flows = FlowStore(session)
        await flows.create_flow(other, "Theirs", graph_using(str(made.id)))
        gone = await flows.create_flow(member, "Gone", graph_using(str(made.id)))
    async with sessions() as session:
        await FlowStore(session).delete_flow(member, gone.id, soft=True)
    async with sessions() as session:
        assert await ConnectionStore(session).flows_using(member, made.id) == []
