import asyncio
import time
from types import SimpleNamespace

import httpx
import pytest

from app.ops import checks

DB_URI = "postgresql+psycopg://u:p@db.test:5432/decisionflow?options=-csearch_path%3Dmlflow"


@pytest.fixture(autouse=True)
def tracing_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    checks._probe_cache.clear()
    monkeypatch.setattr(checks.tracing, "is_configured", lambda: True)


def _refuse(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("down", request=request)


def _use_uri(monkeypatch: pytest.MonkeyPatch, uri: str) -> None:
    monkeypatch.setattr(checks, "get_settings", lambda: SimpleNamespace(mlflow_tracking_uri=uri))


@pytest.mark.anyio
async def test_check_mlflow_is_unavailable_until_tracing_is_configured_and_retries_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_uri(monkeypatch, DB_URI)
    warmed: list[str] = []
    monkeypatch.setattr(checks.tracing, "is_configured", lambda: False)
    monkeypatch.setattr(checks.tracing, "warm_up", lambda s: warmed.append(s.mlflow_tracking_uri))
    monkeypatch.setattr(checks.tracing, "database_reachable", lambda uri, timeout: True)
    assert await checks.check_mlflow() == "unavailable"
    assert warmed == [DB_URI]


@pytest.mark.anyio
@pytest.mark.parametrize(("reachable", "expected"), [(True, "ok"), (False, "unavailable")])
async def test_check_mlflow_database_uri(
    monkeypatch: pytest.MonkeyPatch, reachable: bool, expected: str
) -> None:
    _use_uri(monkeypatch, DB_URI)
    monkeypatch.setattr(checks.tracing, "database_reachable", lambda uri, timeout: reachable)
    assert await checks.check_mlflow() == expected


@pytest.mark.anyio
async def test_check_mlflow_database_uri_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_uri(monkeypatch, DB_URI)
    monkeypatch.setattr(checks, "CHECK_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(
        checks.tracing, "database_reachable", lambda uri, timeout: time.sleep(0.2) or True
    )
    assert await checks.check_mlflow() == "unavailable"


@pytest.mark.anyio
async def test_check_mlflow_probes_the_database_once_per_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_uri(monkeypatch, DB_URI)
    probes: list[str] = []

    def probe(uri: str, timeout: float) -> bool:
        probes.append(uri)
        return True

    monkeypatch.setattr(checks.tracing, "database_reachable", probe)
    assert [await checks.check_mlflow() for _ in range(3)] == ["ok"] * 3
    assert len(probes) == 1

    monkeypatch.setattr(checks, "DATABASE_PROBE_TTL_SECONDS", 0.0)
    await checks.check_mlflow()
    assert len(probes) == 2


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("handler", "expected"),
    [
        (lambda _: httpx.Response(200), "ok"),
        (lambda _: httpx.Response(500), "unavailable"),
        (_refuse, "unavailable"),
    ],
)
async def test_check_mlflow_http_uri(
    monkeypatch: pytest.MonkeyPatch, handler, expected: str
) -> None:
    _use_uri(monkeypatch, "http://mlflow.test:5000")
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        checks.httpx,
        "AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )
    assert await checks.check_mlflow() == expected


class SlowSession:
    async def execute(self, *_args, **_kwargs) -> None:
        await asyncio.sleep(1)


@pytest.mark.anyio
async def test_check_postgres_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(checks, "CHECK_TIMEOUT_SECONDS", 0.01)
    assert await checks.check_postgres(SlowSession()) == "unavailable"
