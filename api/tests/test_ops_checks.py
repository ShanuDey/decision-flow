import asyncio

import httpx
import pytest

from app.ops import checks


def _refuse(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("down", request=request)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("handler", "expected"),
    [
        (lambda _: httpx.Response(200), "ok"),
        (lambda _: httpx.Response(500), "unavailable"),
        (_refuse, "unavailable"),
    ],
)
async def test_check_mlflow(monkeypatch: pytest.MonkeyPatch, handler, expected: str) -> None:
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
