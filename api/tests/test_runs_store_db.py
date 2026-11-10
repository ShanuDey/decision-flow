import uuid
from datetime import datetime, timedelta

import pytest

from app.flows.store import FlowStore
from app.runs import service
from app.runs.models import Run
from app.runs.store import RunStore
from tests.db_fixtures import SessionFactory, anyio_backend  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.anyio]

BASE = datetime(2026, 1, 1, 12, 0, 0, 123456)  # naive, with microseconds like the column


async def flow_id(sessions: SessionFactory) -> uuid.UUID:
    async with sessions() as session:
        return (await FlowStore(session).create_flow("Demo", {})).id


def run(flow: uuid.UUID, **overrides) -> Run:
    fields = dict(
        flow_id=flow,
        status="succeeded",
        test=True,
        input={"amount": 1},
        output={"total": 1},
        error=None,
        duration_ms=3,
    )
    return Run(**{**fields, **overrides})


async def page(store: RunStore, **filters) -> tuple[list[Run], str | None]:
    args = (
        dict(flow_id=None, status=None, test=None, started_from=None, started_to=None, cursor=None)
        | filters
    )
    return await service.list_runs(store, limit=filters.pop("limit", 25), **args)


async def test_a_run_round_trips_through_postgres(sessions: SessionFactory) -> None:
    flow = await flow_id(sessions)
    failed = run(
        flow,
        status="failed",
        output=None,
        error={"node_id": "assign_values", "message": "boom"},
        mlflow_trace_id="tr-abc",
    )
    async with sessions() as session:
        saved = await RunStore(session).add_run(failed)
    async with sessions() as other:
        loaded = await RunStore(other).get_run(saved.id)
    assert loaded is not None
    assert (loaded.status, loaded.output, loaded.mlflow_trace_id) == ("failed", None, "tr-abc")
    assert loaded.error == {"node_id": "assign_values", "message": "boom"}
    assert loaded.input == {"amount": 1} and loaded.started_at is not None


async def test_get_missing_run_is_none(sessions: SessionFactory) -> None:
    async with sessions() as session:
        assert await RunStore(session).get_run(uuid.uuid4()) is None


async def test_keyset_paging_visits_every_run_once_newest_first(sessions: SessionFactory) -> None:
    flow = await flow_id(sessions)
    async with sessions() as session:
        store = RunStore(session)
        for i in range(7):
            await store.add_run(run(flow, started_at=BASE + timedelta(seconds=i)))

        seen, cursor, pages = [], None, 0
        while True:
            rows, cursor = await service.list_runs(
                store,
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
    flow = await flow_id(sessions)
    async with sessions() as session:
        store = RunStore(session)
        for _ in range(5):
            await store.add_run(run(flow, started_at=BASE))  # every run starts at the same instant

        seen, cursor = [], None
        while True:
            rows, cursor = await service.list_runs(
                store,
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
    one, two = await flow_id(sessions), await flow_id(sessions)
    async with sessions() as session:
        store = RunStore(session)
        await store.add_run(run(one, started_at=BASE))
        await store.add_run(run(one, status="failed", started_at=BASE + timedelta(minutes=1)))
        await store.add_run(run(two, test=False, started_at=BASE + timedelta(minutes=2)))
        await store.add_run(run(two, started_at=BASE + timedelta(minutes=3)))

        async def ids(**filters) -> int:
            rows, _ = await service.list_runs(
                store,
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
