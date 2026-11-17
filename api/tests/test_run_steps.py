import uuid
from datetime import timedelta

import httpx
import pytest

from app.main import app
from app.runs.router import get_trace_reader
from app.runs.steps import build_steps
from app.tracing import TraceIncomplete, TraceSpan, TraceUnavailable
from tests.conftest import FakeRunStore, create_flow, example


def span(id: str, parent: str | None, start: int, end: int, **fields: object) -> TraceSpan:
    base = {
        "id": id,
        "parent_id": parent,
        "name": id,
        "span_type": "TASK",
        "node_id": None,
        "node_type": None,
        "ok": True,
        "error": None,
        "start_ns": start,
        "end_ns": end,
        "input": None,
        "output": None,
    }
    return TraceSpan(**{**base, **fields})


def test_build_steps_drops_the_root_and_orders_by_start() -> None:
    spans = [
        span("b", "root", 3_000_000, 4_000_000, node_id="b", node_type="end"),
        span("root", None, 1_000_000, 9_000_000, span_type="CHAIN"),
        span("a", "root", 2_000_000, 2_500_000, node_id="a", node_type="start", output={"x": 1}),
    ]
    steps = build_steps(spans)
    assert [s.id for s in steps] == ["a", "b"]
    assert steps[0].parent_id is None
    assert (steps[0].kind, steps[0].start_offset_ms, steps[0].duration_ms) == ("node", 1.0, 0.5)
    assert steps[0].output == {"x": 1}


def test_build_steps_nests_children_and_maps_kinds() -> None:
    spans = [
        span("root", None, 0, 10, span_type="CHAIN"),
        span("agent", "root", 1, 9, node_id="agent", node_type="agent"),
        span("llm", "agent", 2, 5, span_type="CHAT_MODEL"),
        span("tool", "agent", 5, 7, span_type="TOOL"),
        span("misc", "agent", 7, 8, span_type="RETRIEVER"),
    ]
    by_id = {s.id: s for s in build_steps(spans)}
    assert by_id["llm"].parent_id == "agent"
    assert [by_id[k].kind for k in ("agent", "llm", "tool", "misc")] == [
        "node",
        "llm",
        "tool",
        "other",
    ]


def test_build_steps_reports_failures_and_tolerates_a_missing_parent() -> None:
    spans = [
        span("root", None, 0, 10, span_type="CHAIN"),
        span("n", "gone", 1, 2, node_id="n", ok=False, error="boom"),
    ]
    [step] = build_steps(spans)
    assert (step.status, step.error, step.parent_id) == ("failed", "boom", None)


def test_build_steps_keeps_a_second_root_and_its_children() -> None:
    spans = [
        span("root", None, 0, 20, span_type="CHAIN"),
        span("n", "root", 1, 2, node_id="n"),
        span("stray", None, 5, 9, span_type="CHAIN"),
        span("child", "stray", 6, 8, span_type="TOOL"),
    ]
    by_id = {s.id: s for s in build_steps(spans)}
    assert set(by_id) == {"n", "stray", "child"}
    assert by_id["stray"].parent_id is None
    assert by_id["child"].parent_id == "stray"


def test_build_steps_drops_only_the_earliest_root() -> None:
    spans = [
        span("late", None, 5, 9, span_type="CHAIN"),
        span("root", None, 0, 20, span_type="CHAIN"),
        span("n", "root", 1, 2, node_id="n"),
    ]
    assert [s.id for s in build_steps(spans)] == ["n", "late"]


def test_build_steps_of_nothing_is_empty() -> None:
    assert build_steps([]) == []


class FakeReader:
    def __init__(self) -> None:
        self.spans: list[TraceSpan] | None = None
        self.error: Exception | None = None
        self.calls: list[str] = []

    async def __call__(self, trace_id: str) -> list[TraceSpan] | None:
        self.calls.append(trace_id)
        if self.error:
            raise self.error
        return self.spans


@pytest.fixture
def reader():
    fake = FakeReader()
    app.dependency_overrides[get_trace_reader] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_trace_reader, None)


async def _run_id(client: httpx.AsyncClient) -> str:
    flow = await create_flow(client, example("assign-variable.json"))
    response = await client.post(
        f"/flows/{flow['id']}/runs", json={"test": True, "input": {"amount": 5}}
    )
    return response.json()["run_id"]


@pytest.mark.anyio
async def test_steps_come_from_the_runs_trace(
    client: httpx.AsyncClient, reader: FakeReader
) -> None:
    reader.spans = [
        span("root", None, 0, 5_000_000, span_type="CHAIN"),
        span("s", "root", 1_000_000, 2_000_000, node_id="s", node_type="start", input={"a": 1}),
    ]
    run_id = await _run_id(client)
    response = await client.get(f"/runs/{run_id}/steps")
    assert response.status_code == 200
    body = response.json()
    assert body["pending"] is False
    assert [i["node_type"] for i in body["items"]] == ["start"]
    assert body["items"][0]["input"] == {"a": 1}
    assert reader.calls == ["tr-stub"]


@pytest.mark.anyio
async def test_a_trace_that_is_not_there_yet_is_pending_for_a_fresh_run(
    client: httpx.AsyncClient, reader: FakeReader
) -> None:
    run_id = await _run_id(client)
    assert (await client.get(f"/runs/{run_id}/steps")).json() == {"items": [], "pending": True}


@pytest.mark.anyio
async def test_a_trace_that_never_arrived_stops_being_pending(
    client: httpx.AsyncClient, reader: FakeReader, run_store: FakeRunStore
) -> None:
    run_id = await _run_id(client)
    run = run_store.runs[uuid.UUID(run_id)]
    run.started_at = run.started_at - timedelta(minutes=5)
    assert (await client.get(f"/runs/{run_id}/steps")).json() == {"items": [], "pending": False}


@pytest.mark.anyio
async def test_an_untraced_run_has_no_steps_and_skips_mlflow(
    client: httpx.AsyncClient, reader: FakeReader, run_store: FakeRunStore
) -> None:
    run_id = await _run_id(client)
    run_store.runs[uuid.UUID(run_id)].mlflow_trace_id = None
    assert (await client.get(f"/runs/{run_id}/steps")).json() == {"items": [], "pending": False}
    assert reader.calls == []


@pytest.mark.anyio
async def test_unreadable_trace_store_is_503_in_the_shared_error_shape(
    client: httpx.AsyncClient, reader: FakeReader
) -> None:
    run_id = await _run_id(client)
    reader.error = TraceUnavailable("down")
    response = await client.get(f"/runs/{run_id}/steps")
    assert response.status_code == 503
    assert response.json()["code"] == "trace_unavailable"
    assert (await client.get(f"/runs/{run_id}")).status_code == 200


@pytest.mark.anyio
async def test_a_trace_still_being_written_is_pending_for_a_fresh_run(
    client: httpx.AsyncClient, reader: FakeReader
) -> None:
    run_id = await _run_id(client)
    reader.error = TraceIncomplete("span data missing")
    response = await client.get(f"/runs/{run_id}/steps")
    assert response.status_code == 200
    assert response.json() == {"items": [], "pending": True}


@pytest.mark.anyio
async def test_a_trace_that_stays_incomplete_becomes_a_503(
    client: httpx.AsyncClient, reader: FakeReader, run_store: FakeRunStore
) -> None:
    run_id = await _run_id(client)
    run = run_store.runs[uuid.UUID(run_id)]
    run.started_at = run.started_at - timedelta(minutes=5)
    reader.error = TraceIncomplete("span data missing")
    response = await client.get(f"/runs/{run_id}/steps")
    assert response.status_code == 503
    assert response.json()["code"] == "trace_unavailable"


@pytest.mark.anyio
async def test_steps_of_another_workspaces_run_are_404(
    client: httpx.AsyncClient, reader: FakeReader, run_store: FakeRunStore
) -> None:
    run_id = await _run_id(client)
    run_store.runs[uuid.UUID(run_id)].workspace_id = uuid.uuid4()
    assert (await client.get(f"/runs/{run_id}/steps")).status_code == 404
    assert reader.calls == []


@pytest.mark.anyio
async def test_unknown_run_steps_are_404(client: httpx.AsyncClient, reader: FakeReader) -> None:
    assert (await client.get(f"/runs/{uuid.uuid4()}/steps")).status_code == 404
