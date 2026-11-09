import asyncio
import json
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app import tracing
from app.engine.compiler import compile_graph
from app.engine.runtime import run_flow
from app.engine.validate import parse_graph
from app.settings import Settings

FIXTURE = Path(__file__).resolve().parents[2] / "examples" / "flows" / "start-end.json"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def raw() -> dict:
    return json.loads(FIXTURE.read_text())


def flow(raw: dict):
    graph, issues = parse_graph(raw)
    assert issues == []
    return compile_graph(graph)


class FakeSpan:
    def __init__(
        self, name: str, span_type: str, parent: "FakeSpan | None", attributes: dict, inputs=None
    ):
        self.name, self.span_type, self.parent = name, span_type, parent
        self.attributes = dict(attributes or {})
        self.inputs, self.outputs = inputs, None
        self.trace_id = "tr-fake"
        self.status = None
        self.ended = False

    def end(self, outputs=None, attributes: dict | None = None, status=None) -> None:
        self.outputs = outputs
        self.attributes.update(attributes or {})
        self.status = status
        self.ended = True


class FakeMlflow:
    def __init__(self) -> None:
        self.spans: list[FakeSpan] = []
        self.tracking_uri: str | None = None
        self.experiment: str | None = None
        self.fail = False
        self.autologged = False
        self.langchain = SimpleNamespace(autolog=self._autolog)

    def _autolog(self) -> None:
        self.autologged = True

    def start_span_no_context(
        self, name, span_type="UNKNOWN", parent_span=None, attributes=None, inputs=None
    ):
        if self.fail:
            raise RuntimeError("mlflow is down")
        span = FakeSpan(name, span_type, parent_span, attributes, inputs)
        self.spans.append(span)
        return span

    def set_tracking_uri(self, uri: str) -> None:
        self.tracking_uri = uri

    def set_experiment(self, name: str) -> None:
        if self.fail:
            raise RuntimeError("mlflow is down")
        self.experiment = name


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeMlflow:
    fake = FakeMlflow()
    monkeypatch.setattr(tracing, "mlflow", fake)
    monkeypatch.setattr(tracing, "_configured", True)
    monkeypatch.setattr(tracing, "_warmup", None)
    return fake


def settings() -> Settings:
    return Settings(_env_file=None, mlflow_set_experiment="exp-under-test")


def test_configure_sets_uri_and_experiment_from_settings(
    fake: FakeMlflow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tracing, "_configured", False)
    s = Settings(_env_file=None, mlflow_tracking_uri="http://mlflow.test:5000")
    assert tracing.configure(s) is True
    assert (fake.tracking_uri, fake.experiment) == ("http://mlflow.test:5000", "decision-flow")


def test_configure_reports_failure_instead_of_raising(
    fake: FakeMlflow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tracing, "_configured", False)
    fake.fail = True
    assert tracing.configure(settings()) is False


@pytest.mark.anyio
async def test_run_becomes_one_root_span_with_a_child_span_per_node(
    fake: FakeMlflow, raw: dict
) -> None:
    observer = tracing.MlflowObserver(settings())
    result = await run_flow(flow(raw), {"amount": 1}, observer)

    assert result.status == "succeeded"
    root, start, end = fake.spans
    assert (root.name, root.parent) == ("run", None)
    assert [s.parent for s in (start, end)] == [root, root]
    assert all(s.ended and s.status.status_code.value == "OK" for s in fake.spans)
    assert observer.trace_id == "tr-fake"


@pytest.mark.anyio
async def test_node_spans_are_annotated_with_node_identity(fake: FakeMlflow, raw: dict) -> None:
    await run_flow(flow(raw), {"amount": 1}, tracing.MlflowObserver(settings()))
    start = next(s for s in fake.spans if s.name == "Start")
    assert start.attributes["node_id"] == "start"
    assert start.attributes["node_type"] == "start"
    assert start.attributes["node_name"] == "Start"
    assert start.attributes["duration_ms"] >= 0


def by_name(fake: FakeMlflow) -> dict[str, FakeSpan]:
    return {s.name: s for s in fake.spans}


@pytest.mark.anyio
async def test_inputs_and_outputs_are_recorded_on_the_run_and_every_node(
    fake: FakeMlflow, raw: dict
) -> None:
    await run_flow(flow(raw), {"amount": 5000}, tracing.MlflowObserver(settings()))
    spans = by_name(fake)
    full = {"amount": 5000, "tier": "silver"}
    assert (spans["run"].inputs, spans["run"].outputs) == (full, full)
    assert spans["Start"].inputs["input"] == full
    assert spans["Start"].outputs == full
    assert spans["End"].inputs["input"] == full
    assert spans["End"].outputs == full


@pytest.mark.anyio
async def test_redaction_hook_runs_before_anything_is_recorded(
    fake: FakeMlflow, raw: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tracing, "redact", lambda value: "[redacted]")
    await run_flow(flow(raw), {"amount": 5000}, tracing.MlflowObserver(settings()))
    for span in fake.spans:
        assert span.inputs == "[redacted]" and span.outputs == "[redacted]"


@pytest.mark.anyio
async def test_oversized_values_are_truncated(
    fake: FakeMlflow, raw: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw["nodes"][0]["data"]["inputs"].append({"name": "blob", "type": "string", "required": False})
    monkeypatch.setattr(tracing, "MAX_IO_CHARS", 100)
    await run_flow(flow(raw), {"amount": 1, "blob": "x" * 500}, tracing.MlflowObserver(settings()))
    recorded = by_name(fake)["run"].inputs
    assert recorded["truncated"] is True and recorded["chars"] > 100
    assert len(recorded["preview"]) == 100


@pytest.mark.anyio
async def test_failed_node_marks_its_span_and_the_run_as_error(fake: FakeMlflow, raw: dict) -> None:
    raw["nodes"][0]["data"]["inputs"].append({"name": "note", "type": "string", "required": False})
    raw["nodes"][1]["data"]["outputs"].append(
        {"name": "note", "type": "string", "value": "{{ input.note }}"}
    )
    result = await run_flow(flow(raw), {"amount": 1}, tracing.MlflowObserver(settings()))

    assert result.status == "failed"
    spans = by_name(fake)
    assert spans["End"].status.status_code.value == "ERROR"
    assert "input.note is not set" in spans["End"].status.description
    assert spans["run"].status.status_code.value == "ERROR"
    assert spans["run"].outputs is None


def test_enable_autolog_traces_langgraph_once_mlflow_is_configured(
    fake: FakeMlflow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tracing, "_configured", False)
    tracing.enable_autolog(settings())
    assert fake.autologged is True
    assert fake.experiment == "exp-under-test"


def test_enable_autolog_does_nothing_when_mlflow_is_unreachable(
    fake: FakeMlflow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tracing, "_configured", False)
    fake.fail = True
    tracing.enable_autolog(settings())
    assert fake.autologged is False


@pytest.mark.anyio
async def test_run_goes_untraced_until_mlflow_is_configured_then_recovers(
    fake: FakeMlflow, raw: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tracing, "_configured", False)
    first = tracing.MlflowObserver(settings())
    result = await run_flow(flow(raw), {"amount": 1}, first)
    assert result.status == "succeeded"
    assert fake.spans == [] and first.trace_id is None  # did not wait on MLflow

    assert await tracing.ready() is True
    second = tracing.MlflowObserver(settings())
    await run_flow(flow(raw), {"amount": 1}, second)
    assert second.trace_id == "tr-fake"


@pytest.mark.anyio
async def test_warm_up_is_a_noop_while_one_is_in_flight(
    fake: FakeMlflow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tracing, "_configured", False)
    tracing.warm_up(settings())
    first = tracing._warmup
    tracing.warm_up(settings())
    assert tracing._warmup is first
    await tracing.ready()


def test_app_lifespan_warms_up_tracing_from_settings(fake: FakeMlflow, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setattr(tracing, "_configured", False)
    with TestClient(app):
        pass
    assert fake.experiment == Settings(_env_file=None).mlflow_set_experiment


@pytest.mark.anyio
async def test_mlflow_failure_never_fails_the_run(fake: FakeMlflow, raw: dict) -> None:
    fake.fail = True
    result = await run_flow(flow(raw), {"amount": 1}, tracing.MlflowObserver(settings()))
    assert result.status == "succeeded"
    assert result.output == {"amount": 1, "tier": "silver"}


def _mlflow_up() -> bool:
    try:
        return httpx.get(
            f"{Settings(_env_file=None).mlflow_tracking_uri}/health", timeout=1
        ).is_success
    except httpx.HTTPError:
        return False


def _delete_experiment(base_url: str, name: str) -> None:
    r = httpx.get(
        f"{base_url}/api/2.0/mlflow/experiments/get-by-name", params={"experiment_name": name}
    )
    if r.is_success:
        httpx.post(
            f"{base_url}/api/2.0/mlflow/experiments/delete",
            json={"experiment_id": r.json()["experiment"]["experiment_id"]},
        )


@pytest.mark.skipif(not _mlflow_up(), reason="needs a running MLflow (make mlflow)")
@pytest.mark.anyio
async def test_trace_round_trip_against_a_real_mlflow(raw: dict, monkeypatch) -> None:
    # throwaway experiment, deleted afterwards, so test runs never clutter the dev MLflow
    s = Settings(_env_file=None, mlflow_set_experiment=f"decision-flow-test-{uuid.uuid4().hex[:8]}")
    monkeypatch.setattr(tracing, "_configured", False)
    monkeypatch.setattr(tracing, "_warmup", None)
    try:
        tracing.warm_up(s)  # what the app does at startup
        assert await tracing.ready() is True
        observer = tracing.MlflowObserver(s)
        await run_flow(flow(raw), {"amount": 1}, observer)
        tracing.flush()
        assert observer.trace_id is not None

        spans: list[dict] = []
        deadline = time.monotonic() + 15
        async with httpx.AsyncClient(base_url=s.mlflow_tracking_uri) as client:
            while not spans and time.monotonic() < deadline:
                r = await client.get(
                    "/api/3.0/mlflow/traces/batchGet", params={"trace_ids": observer.trace_id}
                )
                spans = r.json().get("traces", [{}])[0].get("spans", []) if r.is_success else []
                if not spans:
                    await asyncio.sleep(0.2)
        assert {sp["name"] for sp in spans} == {"run", "Start", "End"}
        keys = {a["key"] for sp in spans for a in sp["attributes"]}
        assert {"node_id", "node_type", "node_name"} <= keys
        assert {"mlflow.spanInputs", "mlflow.spanOutputs"} <= keys
    finally:
        _delete_experiment(s.mlflow_tracking_uri, s.mlflow_set_experiment)
