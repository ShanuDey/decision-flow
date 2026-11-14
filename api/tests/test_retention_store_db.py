import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.flows.store import FlowStore
from app.retention.runner import LOCK_KEY, locked_cycle
from app.retention.store import BATCH, RetentionStore
from app.runs.models import Run
from app.runs.store import RunStore
from app.settings import Settings
from app.workspaces.schemas import Member
from tests.db_fixtures import SessionFactory, anyio_backend, make_member  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.anyio]

OLD = timedelta(days=10)


async def add_run(
    sessions: SessionFactory, member: Member, flow: uuid.UUID, age: timedelta
) -> None:
    async with sessions() as session:
        await RunStore(session).add_run(
            Run(
                flow_id=flow,
                workspace_id=member.workspace_id,
                created_by=member.user_id,
                status="succeeded",
                test=True,
                input={},
                output={},
                error=None,
                duration_ms=1,
                started_at=datetime.now(UTC).replace(tzinfo=None) - age,
            )
        )


async def flow_of(sessions: SessionFactory, member: Member) -> uuid.UUID:
    async with sessions() as session:
        return (await FlowStore(session).create_flow(member, "F", {})).id


async def count(sessions: SessionFactory, table: str) -> int:
    async with sessions() as session:
        return await session.scalar(text(f"select count(*) from {table}"))


async def age_user(sessions: SessionFactory, member: Member, age: timedelta) -> None:
    async with sessions() as session:
        await session.execute(
            text("update users set last_seen_at = now() - :age where id = :id"),
            {"age": age, "id": member.user_id},
        )
        await session.commit()


@pytest.fixture
async def auth_schema(sessions: SessionFactory) -> AsyncIterator[None]:
    statements = [
        "create schema if not exists auth",
        'create table auth."user" (id text primary key)',
        'create table auth.session (id text primary key, "userId" text, "expiresAt" timestamp)',
        'create table auth.account (id text primary key, "userId" text)',
    ]
    async with sessions() as session:
        for statement in statements:
            await session.execute(text(statement))
        await session.commit()
    yield
    async with sessions() as session:
        await session.execute(text("drop schema auth cascade"))
        await session.commit()


async def test_old_runs_go_and_recent_ones_stay(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    flow = await flow_of(sessions, member)
    await add_run(sessions, member, flow, OLD)
    await add_run(sessions, member, flow, timedelta(days=1))

    async with sessions() as session:
        assert await RetentionStore(session).delete_runs_older_than(7, dry_run=True) == 1
    assert await count(sessions, "runs") == 2
    async with sessions() as session:
        assert await RetentionStore(session).delete_runs_older_than(7) == 1
    assert await count(sessions, "runs") == 1
    assert await count(sessions, "flows") == 1


async def test_more_than_one_batch_of_runs_is_deleted(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    flow = await flow_of(sessions, member)
    insert = (
        "insert into runs (id, flow_id, workspace_id, created_by, status, test, input, "
        "duration_ms, started_at) select gen_random_uuid(), :f, :w, :u, 'succeeded', true, "
        "'{}', 1, now() - interval '10 days' from generate_series(1, :n)"
    )
    async with sessions() as session:
        await session.execute(
            text(insert),
            {"f": flow, "w": member.workspace_id, "u": member.user_id, "n": BATCH + 5},
        )
        await session.commit()
    async with sessions() as session:
        assert await RetentionStore(session).delete_runs_older_than(7) == BATCH + 5
    assert await count(sessions, "runs") == 0


async def test_an_inactive_user_loses_everything_and_an_active_one_nothing(
    sessions: SessionFactory,
) -> None:
    gone = await make_member(sessions, "gone")
    kept = await make_member(sessions, "kept")
    await add_run(sessions, gone, await flow_of(sessions, gone), timedelta(0))
    await add_run(sessions, kept, await flow_of(sessions, kept), timedelta(0))
    await age_user(sessions, gone, OLD)

    async with sessions() as session:
        assert await RetentionStore(session).delete_inactive_users(7, [], dry_run=True) == 1
    assert await count(sessions, "users") == 2
    async with sessions() as session:
        assert await RetentionStore(session).delete_inactive_users(7, []) == 1
    for table in ("users", "workspaces", "workspace_members", "flows", "runs"):
        assert await count(sessions, table) == 1, table


async def test_the_exempt_list_is_case_insensitive_and_other_users_still_go(
    sessions: SessionFactory,
) -> None:
    owner = await make_member(sessions, "Owner")
    other = await make_member(sessions, "other")
    for member in (owner, other):
        await age_user(sessions, member, OLD)

    async with sessions() as session:
        deleted = await RetentionStore(session).delete_inactive_users(7, ["owner@example.com"])
    assert deleted == 1
    async with sessions() as session:
        emails = (await session.execute(text("select email from users"))).scalars().all()
    assert emails == ["Owner@example.com"]


@pytest.mark.usefixtures("auth_schema")
async def test_deleting_a_user_also_removes_their_sign_in_rows(sessions: SessionFactory) -> None:
    gone = await make_member(sessions, "gone")
    await make_member(sessions, "kept")
    async with sessions() as session:
        for sub in ("gone", "kept"):
            await session.execute(text('insert into auth."user" values (:s)'), {"s": sub})
            await session.execute(text("insert into auth.account values (:s, :s)"), {"s": sub})
            await session.execute(
                text("insert into auth.session values (:s, :s, now() + interval '1 day')"),
                {"s": sub},
            )
        await session.commit()
    await age_user(sessions, gone, OLD)

    async with sessions() as session:
        await RetentionStore(session).delete_inactive_users(7, [])
    for table in ('auth."user"', "auth.account", "auth.session"):
        assert await count(sessions, table) == 1, table


@pytest.mark.usefixtures("auth_schema")
async def test_only_expired_sessions_are_removed(sessions: SessionFactory) -> None:
    async with sessions() as session:
        await session.execute(
            text(
                "insert into auth.session values ('old', 'u', now() - interval '1 day'), "
                "('live', 'u', now() + interval '1 day')"
            )
        )
        await session.commit()
    async with sessions() as session:
        assert await RetentionStore(session).delete_expired_auth_sessions(dry_run=True) == 1
    assert await count(sessions, "auth.session") == 2
    async with sessions() as session:
        assert await RetentionStore(session).delete_expired_auth_sessions() == 1
    assert await count(sessions, "auth.session") == 1


async def test_a_missing_auth_schema_is_skipped(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    await age_user(sessions, member, OLD)
    async with sessions() as session:
        store = RetentionStore(session)
        assert await store.delete_expired_auth_sessions() == 0
        assert await store.delete_inactive_users(7, []) == 1


async def test_a_second_instance_skips_the_cycle_while_the_first_holds_the_lock(
    postgres_url: str,
) -> None:
    engine = create_async_engine(postgres_url)
    settings = Settings(
        _env_file=None, user_retention_days=7, retention_dry_run=True, database_url=postgres_url
    )
    try:
        async with engine.connect() as holder:
            await holder.scalar(select(func.pg_try_advisory_lock(LOCK_KEY)))
            assert await locked_cycle(engine, settings) is None
            await holder.scalar(select(func.pg_advisory_unlock(LOCK_KEY)))
        report = await locked_cycle(engine, settings)
        assert report is not None and report.users == 0
    finally:
        await engine.dispose()


async def test_a_user_seen_recently_is_not_deleted(sessions: SessionFactory) -> None:
    from app.workspaces.store import WorkspaceStore

    member = await make_member(sessions)
    await age_user(sessions, member, OLD)
    async with sessions() as session:
        await WorkspaceStore(session).touch(member.user_id)
    async with sessions() as session:
        assert await RetentionStore(session).delete_inactive_users(7, []) == 0
    assert await count(sessions, "users") == 1
