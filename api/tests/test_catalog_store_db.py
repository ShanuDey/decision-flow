import pytest

from app.catalog.store import InstalledStore
from tests.db_fixtures import SessionFactory, anyio_backend, make_member  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.anyio]

DEFINITION = {"id": "github", "name": "GitHub", "version": "1.0.0"}


async def test_put_then_read_from_another_session(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    async with sessions() as session:
        await InstalledStore(session).put(
            member, "connection-type", "github", "1.0.0", "sha256-a", DEFINITION
        )
    async with sessions() as session:
        store = InstalledStore(session)
        item = await store.get(member, "connection-type", "github")
        listed = await store.list_items(member)
        count = await store.count(member)
    assert item is not None and (item.version, item.hash) == ("1.0.0", "sha256-a")
    assert item.definition == DEFINITION and item.installed_at is not None
    assert [i.item_id for i in listed] == ["github"] and count == 1


async def test_installing_again_replaces_the_item_instead_of_adding_one(
    sessions: SessionFactory,
) -> None:
    member = await make_member(sessions)
    async with sessions() as session:
        await InstalledStore(session).put(
            member, "connection-type", "github", "1.0.0", "sha256-a", DEFINITION
        )
    async with sessions() as session:
        updated = await InstalledStore(session).put(
            member,
            "connection-type",
            "github",
            "1.1.0",
            "sha256-b",
            {**DEFINITION, "version": "1.1.0"},
        )
    assert (updated.version, updated.hash) == ("1.1.0", "sha256-b")
    async with sessions() as session:
        store = InstalledStore(session)
        assert await store.count(member) == 1
        item = await store.get(member, "connection-type", "github")
    assert item is not None and item.definition["version"] == "1.1.0"


async def test_a_kind_and_an_id_are_separate_keys(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    async with sessions() as session:
        store = InstalledStore(session)
        await store.put(member, "connection-type", "x", "1.0.0", "h1", {})
        await store.put(member, "node-template", "x", "1.0.0", "h2", {})
    async with sessions() as session:
        store = InstalledStore(session)
        assert await store.count(member) == 2
        assert [i.kind for i in await store.list_items(member, "node-template")] == [
            "node-template"
        ]


async def test_delete_removes_it_and_reports_whether_it_was_there(
    sessions: SessionFactory,
) -> None:
    member = await make_member(sessions)
    async with sessions() as session:
        await InstalledStore(session).put(member, "connection-type", "github", "1.0.0", "h", {})
    async with sessions() as session:
        assert await InstalledStore(session).delete(member, "connection-type", "github") is True
    async with sessions() as session:
        store = InstalledStore(session)
        assert await store.delete(member, "connection-type", "github") is False
        assert await store.get(member, "connection-type", "github") is None


async def test_another_workspace_sees_and_changes_nothing(sessions: SessionFactory) -> None:
    owner = await make_member(sessions)
    other = await make_member(sessions, "user-2")
    async with sessions() as session:
        await InstalledStore(session).put(owner, "connection-type", "github", "1.0.0", "h", {})
    async with sessions() as session:
        store = InstalledStore(session)
        assert await store.list_items(other) == []
        assert await store.get(other, "connection-type", "github") is None
        assert await store.delete(other, "connection-type", "github") is False
        assert await store.count(owner) == 1
