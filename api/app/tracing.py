"""MLflow tracing adapter, the only importer of mlflow. MLflow failures never fail a run."""

import asyncio
import json
import logging
import math
import re
from typing import Any

import mlflow
from mlflow.entities import SpanStatus, SpanStatusCode, SpanType
from mlflow.environment_variables import (
    MLFLOW_HTTP_REQUEST_MAX_RETRIES,
    MLFLOW_HTTP_REQUEST_TIMEOUT,
)
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

from app.engine.observer import NodeInfo, NodeStatus, RunStatus
from app.settings import Settings, query_options

log = logging.getLogger(__name__)

DB_CONNECT_TIMEOUT_SECONDS = 3.0
LOOPBACK_HOSTS = {None, "", "localhost", "127.0.0.1", "::1"}

_configured = False
_warmup: "asyncio.Task[bool] | None" = None


def is_configured() -> bool:
    return _configured


def database_error(uri: str, timeout: float = DB_CONNECT_TIMEOUT_SECONDS) -> str | None:
    """Blocking. None if reachable, and always for non-Postgres URIs (HTTP is probed elsewhere)."""
    try:
        url = make_url(uri)
        if url.get_backend_name() != "postgresql":
            return None
        engine = create_engine(url, connect_args={"connect_timeout": math.ceil(timeout)})
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        finally:
            engine.dispose()
    except Exception as exc:
        lines = str(exc).strip().splitlines()
        return f"{type(exc).__name__}: {lines[0] if lines else ''}"
    return None


def database_reachable(uri: str, timeout: float = DB_CONNECT_TIMEOUT_SECONDS) -> bool:
    return database_error(uri, timeout) is None


def _same_server(a: URL, b: URL) -> bool:
    def endpoint(url: URL) -> tuple[str | None, int]:
        host = "localhost" if url.host in LOOPBACK_HOSTS else url.host.lower()
        return host, url.port or 5432

    return endpoint(a) == endpoint(b)


def _search_path_schema(options: str) -> str | None:
    match = re.search(r"search_path=([^\s,]+)", options)
    return match.group(1) if match else None


def writes_into_app_schema(settings: Settings) -> bool:
    """True if MLflow would create its tables beside ours (its `runs` table would clash)."""
    try:
        tracking, app = make_url(settings.mlflow_tracking_uri), make_url(settings.database_url)
    except Exception:
        return False
    if tracking.get_backend_name() != "postgresql" or app.get_backend_name() != "postgresql":
        return False
    if not _same_server(tracking, app) or tracking.database != app.database:
        return False
    return _search_path_schema(query_options(tracking)) in (None, "public")


def configure(settings: Settings) -> bool:
    """Blocking; returns False if MLflow is unreachable."""
    global _configured
    if writes_into_app_schema(settings):
        log.error("MLFLOW_TRACKING_URI shares the app database without a search_path; not tracing")
        return False
    # MLflow's defaults retry for minutes; a down server must not stall startup or runs
    MLFLOW_HTTP_REQUEST_MAX_RETRIES.set(1)
    MLFLOW_HTTP_REQUEST_TIMEOUT.set(5)
    # MLflow's own database retry (10 tries, ~100 s of backoff, no setting) must not hit a dead DB
    error = database_error(settings.mlflow_tracking_uri)
    if error is not None:
        log.warning("MLflow database unreachable (%s); runs will not be traced", error)
        return False
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
