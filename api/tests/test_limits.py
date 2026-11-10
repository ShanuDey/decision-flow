from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI

from app.limits import install_body_limit
from tests.conftest import create_flow

CAP = 100


@pytest.fixture
async def small() -> AsyncIterator[httpx.AsyncClient]:
    app = FastAPI()
    install_body_limit(app, CAP)

    @app.post("/echo")
    async def echo(body: dict) -> dict:
        return body

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        yield c


JSON = {"content-type": "application/json"}


def payload(size: int) -> bytes:
    """Valid JSON of exactly `size` bytes."""
    return b'{"x": "' + b"a" * (size - 9) + b'"}'


@pytest.mark.anyio
async def test_a_body_at_the_cap_passes(small: httpx.AsyncClient) -> None:
    response = await small.post("/echo", content=payload(CAP), headers=JSON)
    assert response.status_code == 200


@pytest.mark.anyio
async def test_declared_length_over_the_cap_is_413_in_the_shared_shape(
    small: httpx.AsyncClient,
) -> None:
    response = await small.post("/echo", content=payload(CAP + 1), headers=JSON)
    assert response.status_code == 413
    assert response.json() == {
        "code": "payload_too_large",
        "message": f"Request body is larger than {CAP} bytes",
        "details": {"max_bytes": CAP},
    }


@pytest.mark.anyio
async def test_chunked_body_over_the_cap_is_413(small: httpx.AsyncClient) -> None:
    async def chunks() -> AsyncIterator[bytes]:
        for _ in range(5):
            yield b'{"a": "' + b"b" * 30 + b'"}'

    request = small.build_request("POST", "/echo", content=chunks(), headers=JSON)
    assert "content-length" not in request.headers  # chunked: no length up front
    response = await small.send(request)
    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"


@pytest.mark.anyio
async def test_oversized_flow_draft_is_refused_by_the_real_app(client: httpx.AsyncClient) -> None:
    flow = await create_flow(client)
    huge = {"schema_version": 1, "padding": "x" * (1_048_576 + 1)}
    response = await client.put(f"/flows/{flow['id']}/draft", json=huge, headers={"If-Match": "1"})
    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"
