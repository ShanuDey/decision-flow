from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.limits import Limits, install_body_limit
from tests.conftest import create_flow

CAP = 100


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for name in Limits.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    return monkeypatch


@pytest.mark.usefixtures("clean_env")
def test_defaults() -> None:
    limits = Limits(_env_file=None)
    assert limits.max_request_bytes == 1_048_576
    assert limits.max_concurrent_runs == 10
    assert limits.max_concurrent_runs_per_workspace == 0
    assert limits.run_timeout_seconds == 300


def test_environment_overrides_the_defaults(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("MAX_CONCURRENT_RUNS_PER_WORKSPACE", "2")
    clean_env.setenv("RUN_TIMEOUT_SECONDS", "30")
    limits = Limits(_env_file=None)
    assert (limits.max_concurrent_runs_per_workspace, limits.run_timeout_seconds) == (2, 30)


@pytest.mark.usefixtures("clean_env")
def test_zero_turns_a_run_limit_off() -> None:
    limits = Limits(_env_file=None, max_concurrent_runs=0, run_timeout_seconds=0)
    assert (limits.max_concurrent_runs, limits.run_timeout_seconds) == (0, 0)


@pytest.mark.usefixtures("clean_env")
@pytest.mark.parametrize(
    "field", ["max_request_bytes", "max_concurrent_runs", "run_timeout_seconds"]
)
def test_a_negative_limit_is_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        Limits(_env_file=None, **{field: -1})


@pytest.mark.usefixtures("clean_env")
def test_the_body_cap_cannot_be_switched_off() -> None:
    with pytest.raises(ValidationError):
        Limits(_env_file=None, max_request_bytes=0)


@pytest.mark.usefixtures("clean_env")
def test_limits_are_frozen() -> None:
    with pytest.raises(ValidationError):
        Limits(_env_file=None).max_concurrent_runs = 99  # type: ignore[misc]


@pytest.mark.usefixtures("clean_env")
def test_there_is_no_notice_unless_one_is_set() -> None:
    assert Limits(_env_file=None).notice_details() == {}
    assert Limits(_env_file=None, limit_notice_url="https://x.test").notice_details() == {}


@pytest.mark.usefixtures("clean_env")
def test_a_notice_is_trimmed_and_carries_its_link() -> None:
    limits = Limits(
        _env_file=None, limit_notice="  Free demo.  ", limit_notice_url="https://x.test"
    )
    assert limits.notice_details() == {"notice": "Free demo.", "notice_url": "https://x.test"}
    assert Limits(_env_file=None, limit_notice="Free demo.").notice_details() == {
        "notice": "Free demo."
    }


def test_the_notice_comes_from_the_environment(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("LIMIT_NOTICE", "Free demo.")
    assert Limits(_env_file=None).notice_details() == {"notice": "Free demo."}


@pytest.mark.usefixtures("clean_env")
def test_a_long_notice_or_a_non_web_link_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Limits(_env_file=None, limit_notice="x" * 301)
    for bad in ("javascript:alert(1)", "ftp://x.test", "x.test"):
        with pytest.raises(ValidationError):
            Limits(_env_file=None, limit_notice="n", limit_notice_url=bad)


@pytest.mark.anyio
async def test_the_413_carries_the_notice_when_one_is_set() -> None:
    app = FastAPI()
    install_body_limit(app, CAP, {"notice": "Free demo."})

    @app.post("/echo")
    async def echo(body: dict) -> dict:
        return body

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        response = await c.post("/echo", content=payload(CAP + 1), headers=JSON)
    assert response.status_code == 413
    assert response.json()["details"] == {"max_bytes": CAP, "notice": "Free demo."}


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
