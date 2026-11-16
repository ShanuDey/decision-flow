import pytest

from app.secrets.store import SecretStore
from tests.db_fixtures import SessionFactory, anyio_backend, make_member  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.anyio]


async def test_put_inserts_then_replaces_in_place(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    async with sessions() as session:
        store = SecretStore(session)
        first = await store.put(member, "STRIPE_KEY", "cipher-1")
        second = await store.put(member, "STRIPE_KEY", "cipher-2")

    assert second.id == first.id
    assert second.value_encrypted == "cipher-2"
    assert second.updated_at >= first.created_at
    async with sessions() as session:
        assert await SecretStore(session).count(member) == 1


async def test_secrets_are_scoped_to_the_workspace(sessions: SessionFactory) -> None:
    mine = await make_member(sessions, "user-1")
    theirs = await make_member(sessions, "user-2")
    async with sessions() as session:
        store = SecretStore(session)
        await store.put(mine, "STRIPE_KEY", "cipher-1")
        await store.put(theirs, "STRIPE_KEY", "cipher-2")

        assert [s.value_encrypted for s in await store.list_secrets(mine)] == ["cipher-1"]
        assert not await store.exists(mine, "OTHER_KEY")
        assert await store.delete(theirs, "STRIPE_KEY")
        assert not await store.delete(theirs, "STRIPE_KEY")
        assert await store.exists(mine, "STRIPE_KEY")


async def test_listing_is_sorted_by_name(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    async with sessions() as session:
        store = SecretStore(session)
        for name in ("ZETA_KEY", "ALPHA_KEY", "MID_KEY"):
            await store.put(member, name, "cipher")

        assert [s.name for s in await store.list_secrets(member)] == [
            "ALPHA_KEY",
            "MID_KEY",
            "ZETA_KEY",
        ]
