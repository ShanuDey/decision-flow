import httpx
import pytest

from app.db import get_session
from app.main import app


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
    ("fail", "code", "status"), [(False, 200, "ok"), (True, 503, "unavailable")]
)
async def test_ready(client: httpx.AsyncClient, fail: bool, code: int, status: str) -> None:
    app.dependency_overrides[get_session] = lambda: FakeSession(fail)
    try:
        response = await client.get("/ready")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == code
    assert response.json()["status"] == status
