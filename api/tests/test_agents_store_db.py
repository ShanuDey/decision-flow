import asyncio
import uuid
from typing import Any

import pytest
from sqlalchemy import func, select

from app.agents.models import AgentMessage
from app.agents.store import AgentStore, NameTaken, NewMessage, ThreadBusy
from app.connections.store import ConnectionStore
from app.workspaces.schemas import Member
from tests.db_fixtures import SessionFactory, anyio_backend, make_member  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.anyio]


def fields(**changes: Any) -> dict[str, Any]:
    base = {
        "description": "",
        "connection_id": None,
        "model": "",
        "instructions": "",
        "tools": [],
        "settings": {},
    }
    return base | changes


async def make_agent(sessions: SessionFactory, member: Member, name: str = "Helper", **more: Any):
    async with sessions() as session:
        return await AgentStore(session).add(member, name, fields(**more))


async def test_an_agent_round_trips_with_its_tools_and_settings(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    tool = {"flow_id": str(uuid.uuid4()), "name": "double", "description": "Doubles"}
    made = await make_agent(
        sessions, member, tools=[tool], settings={"max_iterations": 3}, instructions="Be brief"
    )
    async with sessions() as session:
        loaded = await AgentStore(session).get(member, made.id)
    assert loaded is not None
    assert (loaded.tools, loaded.settings, loaded.instructions) == (
        [tool],
        {"max_iterations": 3},
        "Be brief",
    )
    assert loaded.created_by == member.user_id and loaded.created_at


async def test_names_are_unique_per_workspace_only(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    stranger = await make_member(sessions, "user-2")
    await make_agent(sessions, member)
    await make_agent(sessions, stranger)
    with pytest.raises(NameTaken):
        await make_agent(sessions, member)
    other = await make_agent(sessions, member, "Other")
    async with sessions() as session:
        with pytest.raises(NameTaken):
            await AgentStore(session).replace(member, other.id, "Helper", fields())


async def test_another_workspace_cannot_read_change_or_delete_an_agent(
    sessions: SessionFactory,
) -> None:
    member = await make_member(sessions)
    stranger = await make_member(sessions, "user-2")
    made = await make_agent(sessions, member)
    async with sessions() as session:
        store = AgentStore(session)
        assert await store.get(stranger, made.id) is None
        assert await store.replace(stranger, made.id, "Mine now", fields()) is None
        assert await store.delete(stranger, made.id) is False
        assert await store.list_agents(stranger) == []
        assert await store.get(member, made.id) is not None


async def test_messages_get_the_next_positions_and_the_first_one_titles_the_thread(
    sessions: SessionFactory,
) -> None:
    member = await make_member(sessions)
    made = await make_agent(sessions, member)
    async with sessions() as session:
        store = AgentStore(session)
        thread = await store.create_thread(member, made.id)
        first = await store.add_messages(
            thread,
            [
                NewMessage("user", "Hi"),
                NewMessage("assistant", "Hello", steps=[], usage={"total_tokens": 5}, model="m"),
            ],
            "Hi",
        )
        second = await store.add_messages(thread, [NewMessage("user", "More")], "More")
    assert [m.seq for m in first] == [1, 2] and [m.seq for m in second] == [3]
    async with sessions() as session:
        store = AgentStore(session)
        loaded = await store.get_thread(member, made.id, thread.id)
        rows = await store.list_messages(thread.id)
    assert loaded is not None and loaded.title == "Hi"
    assert [(m.seq, m.role) for m in rows] == [(1, "user"), (2, "assistant"), (3, "user")]
    assert rows[1].usage == {"total_tokens": 5} and rows[1].model == "m"


async def test_two_answers_at_once_cannot_take_the_same_position(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    made = await make_agent(sessions, member)
    async with sessions() as session:
        thread = await AgentStore(session).create_thread(member, made.id)

    async def add(text: str) -> str:
        async with sessions() as session:
            try:
                await AgentStore(session).add_messages(thread, [NewMessage("user", text)], text)
            except ThreadBusy:
                return "busy"
        return "ok"

    results = await asyncio.gather(*(add(str(i)) for i in range(8)))
    async with sessions() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(AgentMessage)
            .where(AgentMessage.thread_id == thread.id)
        )
    assert results.count("ok") == count and results.count("ok") >= 1


async def test_threads_belong_to_the_person_who_started_them(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    made = await make_agent(sessions, member)
    async with sessions() as session:
        store = AgentStore(session)
        mine = await store.create_thread(member, made.id)
        assert [t.id for t in await store.list_threads(member, made.id, 10)] == [mine.id]
        assert await store.get_thread(member, made.id, uuid.uuid4()) is None
        assert await store.delete_thread(member, made.id, mine.id) is True
        assert await store.list_threads(member, made.id, 10) == []


async def test_deleting_an_agent_removes_its_threads_and_messages(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    made = await make_agent(sessions, member)
    async with sessions() as session:
        store = AgentStore(session)
        thread = await store.create_thread(member, made.id)
        await store.add_messages(thread, [NewMessage("user", "Hi")], "Hi")
        assert await store.delete(member, made.id) is True
    async with sessions() as session:
        left = await session.scalar(select(func.count()).select_from(AgentMessage))
    assert left == 0


async def test_deleting_a_connection_clears_it_from_the_agents_that_used_it(
    sessions: SessionFactory,
) -> None:
    member = await make_member(sessions)
    async with sessions() as session:
        conn = await ConnectionStore(session).add(member, "bearer", "Key", {}, "x")
    made = await make_agent(sessions, member, connection_id=conn.id)
    async with sessions() as session:
        assert [a.id for a in await ConnectionStore(session).agents_using(member, conn.id)] == [
            made.id
        ]
        assert await ConnectionStore(session).delete(member, conn.id) is True
    async with sessions() as session:
        loaded = await AgentStore(session).get(member, made.id)
    assert loaded is not None and loaded.connection_id is None


async def test_a_message_keeps_the_trace_it_was_answered_with(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    made = await make_agent(sessions, member)
    async with sessions() as session:
        store = AgentStore(session)
        thread = await store.create_thread(member, made.id)
        user, reply = await store.add_messages(
            thread,
            [NewMessage("user", "Hi"), NewMessage("assistant", "Hello", trace_id="tr-1")],
            "Hi",
        )
    async with sessions() as session:
        store = AgentStore(session)
        loaded = await store.get_message(thread.id, reply.id)
        plain = await store.get_message(thread.id, user.id)
        elsewhere = await store.get_message(uuid.uuid4(), reply.id)
    assert loaded is not None and loaded.trace_id == "tr-1"
    assert plain is not None and plain.trace_id is None and elsewhere is None
