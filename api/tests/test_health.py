import httpx
import pytest

from app.db import get_session
from app.main import app
from app.routes import health


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.anyio
async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


class FakeSession:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def execute(self, *_args, **_kwargs) -> None:
        if self.fail:
            raise ConnectionError("db down")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("db_down", "mlflow", "code", "status"),
    [
        (False, "ok", 200, "ok"),
        (True, "ok", 503, "unavailable"),
        (False, "unavailable", 503, "unavailable"),
        (True, "unavailable", 503, "unavailable"),
    ],
)
async def test_ready(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    db_down: bool,
    mlflow: str,
    code: int,
    status: str,
) -> None:
    async def fake_mlflow() -> str:
        return mlflow

    monkeypatch.setattr(health, "_check_mlflow", fake_mlflow)
    app.dependency_overrides[get_session] = lambda: FakeSession(db_down)
    try:
        response = await client.get("/ready")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == code
    body = response.json()
    assert body["status"] == status
    assert body["checks"] == {"postgres": "unavailable" if db_down else "ok", "mlflow": mlflow}


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
        health.httpx,
        "AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )
    assert await health._check_mlflow() == expected
