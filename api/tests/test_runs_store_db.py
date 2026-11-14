import uuid
from datetime import datetime, timedelta

import pytest

from app.flows.store import FlowStore
from app.runs import service
from app.runs.models import Run
from app.runs.store import FlowGone, RunStore
from app.workspaces.schemas import Member
from tests.db_fixtures import SessionFactory, anyio_backend, make_member  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.anyio]

BASE = datetime(2026, 1, 1, 12, 0, 0, 123456)  # naive, with microseconds like the column


async def flow_id(sessions: SessionFactory, member: Member) -> uuid.UUID:
    async with sessions() as session:
        return (await FlowStore(session).create_flow(member, "Demo", {})).id


def run(flow: uuid.UUID, member: Member, **overrides) -> Run:
    fields = dict(
        flow_id=flow,
        workspace_id=member.workspace_id,
        created_by=member.user_id,
        status="succeeded",
        test=True,
        input={"amount": 1},
        output={"total": 1},
        error=None,
        duration_ms=3,
    )
    return Run(**{**fields, **overrides})


async def page(store: RunStore, member: Member, **filters) -> tuple[list[Run], str | None]:
    args = (
        dict(flow_id=None, status=None, test=None, started_from=None, started_to=None, cursor=None)
        | filters
    )
    return await service.list_runs(store, member, limit=filters.pop("limit", 25), **args)


async def test_a_run_round_trips_through_postgres(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    flow = await flow_id(sessions, member)
    failed = run(
        flow,
        member,
        status="failed",
        output=None,
        error={"node_id": "assign_values", "message": "boom"},
        mlflow_trace_id="tr-abc",
    )
    async with sessions() as session:
        saved = await RunStore(session).add_run(failed)
    async with sessions() as other:
        loaded = await RunStore(other).get_run(member, saved.id)
    assert loaded is not None
    assert (loaded.status, loaded.output, loaded.mlflow_trace_id) == ("failed", None, "tr-abc")
    assert loaded.error == {"node_id": "assign_values", "message": "boom"}
    assert loaded.input == {"amount": 1} and loaded.started_at is not None
    assert (loaded.workspace_id, loaded.created_by) == (member.workspace_id, member.user_id)


async def test_get_missing_run_is_none(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    async with sessions() as session:
        assert await RunStore(session).get_run(member, uuid.uuid4()) is None


async def test_keyset_paging_visits_every_run_once_newest_first(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    flow = await flow_id(sessions, member)
    async with sessions() as session:
        store = RunStore(session)
        for i in range(7):
            await store.add_run(run(flow, member, started_at=BASE + timedelta(seconds=i)))

        seen, cursor, pages = [], None, 0
        while True:
            rows, cursor = await service.list_runs(
                store,
                member,
                flow_id=None,
                status=None,
                test=None,
                started_from=None,
                started_to=None,
                cursor=cursor,
                limit=3,
            )
            seen += rows
            pages += 1
            if cursor is None:
                break
    assert pages == 3
    assert [r.started_at for r in seen] == [BASE + timedelta(seconds=i) for i in range(6, -1, -1)]
    assert len({r.id for r in seen}) == 7


async def test_identical_timestamps_page_by_id_without_gaps_or_repeats(
    sessions: SessionFactory,
) -> None:
    member = await make_member(sessions)
    flow = await flow_id(sessions, member)
    async with sessions() as session:
        store = RunStore(session)
        for _ in range(5):
            # every run starts at the same instant
            await store.add_run(run(flow, member, started_at=BASE))

        seen, cursor = [], None
        while True:
            rows, cursor = await service.list_runs(
                store,
                member,
                flow_id=None,
                status=None,
                test=None,
                started_from=None,
                started_to=None,
                cursor=cursor,
                limit=2,
            )
            seen += rows
            if cursor is None:
                break
    ids = [r.id for r in seen]
    assert len(ids) == 5 and len(set(ids)) == 5
    assert ids == sorted(ids, reverse=True)  # id is the tiebreak, descending like the time


async def test_filters(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    one, two = await flow_id(sessions, member), await flow_id(sessions, member)
    async with sessions() as session:
        store = RunStore(session)
        await store.add_run(run(one, member, started_at=BASE))
        await store.add_run(
            run(one, member, status="failed", started_at=BASE + timedelta(minutes=1))
        )
        await store.add_run(run(two, member, test=False, started_at=BASE + timedelta(minutes=2)))
        await store.add_run(run(two, member, started_at=BASE + timedelta(minutes=3)))

        async def ids(**filters) -> int:
            rows, _ = await service.list_runs(
                store,
                member,
                flow_id=filters.get("flow_id"),
                status=filters.get("status"),
                test=filters.get("test"),
                started_from=filters.get("started_from"),
                started_to=filters.get("started_to"),
                cursor=None,
                limit=25,
            )
            return len(rows)

        assert await ids() == 4
        assert await ids(flow_id=one) == 2
        assert await ids(status="failed") == 1
        assert await ids(test=False) == 1
        assert await ids(started_from=BASE + timedelta(minutes=1)) == 3
        assert await ids(started_to=BASE + timedelta(minutes=1)) == 2
        assert await ids(flow_id=two, status="succeeded", test=True) == 1


async def test_another_workspace_sees_no_runs(sessions: SessionFactory) -> None:
    owner, outsider = await make_member(sessions, "a"), await make_member(sessions, "b")
    flow = await flow_id(sessions, owner)
    async with sessions() as session:
        saved = await RunStore(session).add_run(run(flow, owner, started_at=BASE))
    async with sessions() as other:
        store = RunStore(other)
        assert await store.get_run(outsider, saved.id) is None
        assert (await page(store, outsider))[0] == []
        assert len((await page(store, owner))[0]) == 1


async def test_deleting_a_flow_removes_its_runs_and_only_its_own(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    gone, kept = await flow_id(sessions, member), await flow_id(sessions, member)
    async with sessions() as session:
        runs = RunStore(session)
        doomed = await runs.add_run(run(gone, member))
        survivor = await runs.add_run(run(kept, member))

    async with sessions() as session:
        assert await FlowStore(session).delete_flow(member, gone) is True

    async with sessions() as session:
        runs = RunStore(session)
        assert await runs.get_run(member, doomed.id) is None
        assert await runs.get_run(member, survivor.id) is not None


async def test_a_run_for_a_deleted_flow_raises_flow_gone(sessions: SessionFactory) -> None:
    member = await make_member(sessions)
    flow = await flow_id(sessions, member)
    async with sessions() as session:
        await FlowStore(session).delete_flow(member, flow)
    async with sessions() as session:
        with pytest.raises(FlowGone):
            await RunStore(session).add_run(run(flow, member))
