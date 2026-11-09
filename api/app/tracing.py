"""MLflow tracing adapter. The only module that imports mlflow.

A run is one trace: a root span plus one child span per node. MLflow being down must never fail
a run, so every MLflow call here is guarded.
"""

import asyncio
import json
import logging
from typing import Any

import mlflow
from mlflow.entities import SpanStatus, SpanStatusCode, SpanType
from mlflow.environment_variables import (
    MLFLOW_HTTP_REQUEST_MAX_RETRIES,
    MLFLOW_HTTP_REQUEST_TIMEOUT,
)

from app.engine.observer import NodeInfo, NodeStatus, RunStatus
from app.settings import Settings

log = logging.getLogger(__name__)

_configured = False
_warmup: "asyncio.Task[bool] | None" = None


def configure(settings: Settings) -> bool:
    """Point MLflow at the server and select the experiment. Blocking; False if unreachable."""
    global _configured
    # MLflow's defaults retry for minutes; a down server must not stall startup or runs
    MLFLOW_HTTP_REQUEST_MAX_RETRIES.set(1)
    MLFLOW_HTTP_REQUEST_TIMEOUT.set(5)
    try:
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        mlflow.set_experiment(settings.mlflow_set_experiment)
    except Exception:
        log.warning("MLflow tracing unavailable; runs will not be traced", exc_info=True)
        return False
    _configured = True
    return True


def enable_autolog(settings: Settings) -> None:
    """Trace every LangGraph call automatically; for dev tools that call graphs directly."""
    if configure(settings):
        mlflow.langchain.autolog()


def warm_up(settings: Settings) -> None:
    """Configure in the background (first call takes seconds); never blocks, never raises."""
    global _warmup
    if _configured or (_warmup is not None and not _warmup.done()):
        return
    _warmup = asyncio.create_task(asyncio.to_thread(configure, settings))


async def ready() -> bool:
    if _warmup is not None:
        await _warmup
    return _configured


def flush() -> None:
    """Block until queued traces are exported (tests and graceful shutdown)."""
    try:
        mlflow.flush_trace_async_logging()
    except Exception:
        log.warning("MLflow trace flush failed", exc_info=True)


async def shutdown() -> None:
    await ready()
    await asyncio.to_thread(flush)


def _guarded(method: Any) -> Any:
    async def wrapper(self: "MlflowObserver", *args: Any, **kwargs: Any) -> None:
        try:
            await method(self, *args, **kwargs)
        except Exception:
            log.warning("MLflow tracing call failed", exc_info=True)

    return wrapper


MAX_IO_CHARS = 10_000


def redact(value: Any) -> Any:
    """Placeholder: the secrets redactor plugs in here before anything is recorded."""
    return value


def _record(value: Any) -> Any:
    """Redact, then cap the size so one huge payload cannot bloat the trace store."""
    value = redact(value)
    text = json.dumps(value, default=str)
    if len(text) <= MAX_IO_CHARS:
        return value
    return {"truncated": True, "chars": len(text), "preview": text[:MAX_IO_CHARS]}


def _io(value: Any) -> Any:
    return _record(value) if value is not None else None


def _status(ok: bool, error: str | None) -> SpanStatus:
    if ok:
        return SpanStatus(SpanStatusCode.OK)
    return SpanStatus(SpanStatusCode.ERROR, error or "failed")


class MlflowObserver:
    """Engine Observer that records one trace per run. Create one per run."""

    def __init__(self, settings: Settings, run_name: str = "run") -> None:
        self._settings = settings
        self._run_name = run_name
        self._root: Any = None
        self._spans: dict[str, Any] = {}
        self.trace_id: str | None = None

    @_guarded
    async def run_started(self, inputs: dict[str, Any]) -> None:
        if not _configured:
            # startup missed MLflow: this run goes untraced rather than waiting on it
            warm_up(self._settings)
            return
        self._root = mlflow.start_span_no_context(
            self._run_name, span_type=SpanType.CHAIN, inputs=_io(inputs)
        )
        self.trace_id = self._root.trace_id

    @_guarded
    async def node_started(self, node: NodeInfo, inputs: dict[str, Any]) -> None:
        if self._root is None:
            return
        self._spans[node.id] = mlflow.start_span_no_context(
            node.name,
            span_type=SpanType.TASK,
            parent_span=self._root,
            inputs=_io(inputs),
            attributes={"node_id": node.id, "node_type": node.type, "node_name": node.name},
        )

    @_guarded
    async def node_finished(
        self,
        node: NodeInfo,
        status: NodeStatus,
        duration_ms: int,
        error: str | None,
        outputs: Any = None,
    ) -> None:
        span = self._spans.pop(node.id, None)
        if span is not None:
            span.end(
                outputs=_io(outputs),
                attributes={"duration_ms": duration_ms},
                status=_status(status == "ok", error),
            )

    @_guarded
    async def run_finished(
        self, status: RunStatus, error: str | None, outputs: dict[str, Any] | None = None
    ) -> None:
        if self._root is not None:
            self._root.end(outputs=_io(outputs), status=_status(status == "succeeded", error))
            self._root = None
