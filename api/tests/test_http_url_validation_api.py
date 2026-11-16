from collections.abc import Iterator

import httpx
import pytest

from app.main import app
from app.security.ssrf import OutboundPolicy
from app.settings import Settings, get_settings
from tests.conftest import create_flow
from tests.test_node_http_request import flow as http_flow

pytestmark = pytest.mark.anyio


@pytest.fixture
def restricted(monkeypatch: pytest.MonkeyPatch) -> Iterator[OutboundPolicy]:
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, allow_private_networks=False, http_allowed_hosts="api.example.com"
    )
    policy = OutboundPolicy(
        allow_private=False,
        allowed_hosts=("api.example.com",),
        max_bytes=1000,
        timeout_seconds=5,
    )
    monkeypatch.setattr("app.runs.router.outbound_policy", lambda _settings, _limits: policy)
    yield policy
    app.dependency_overrides.pop(get_settings, None)


def draft_calling(url: str) -> dict:
    return http_flow({"url": url}, [])


async def test_validate_publish_and_run_all_refuse_a_host_the_server_would_refuse(
    client: httpx.AsyncClient, restricted: OutboundPolicy
) -> None:
    flow = await create_flow(client, draft_calling("https://other.example.com/x"))

    validate = await client.post(f"/flows/{flow['id']}/validate")
    publish = await client.post(f"/flows/{flow['id']}/publish", headers={"If-Match": "1"})
    run = await client.post(f"/flows/{flow['id']}/runs?wait=true", json={"test": True})

    for response in (validate, publish, run):
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "invalid_flow"
        error = response.json()["details"]["errors"][0]
        assert (error["code"], error["field"]) == ("host_not_allowed", "data.url")
        assert "api.example.com" in error["message"]


async def test_the_same_flow_is_valid_for_an_allowed_host(
    client: httpx.AsyncClient, restricted: OutboundPolicy
) -> None:
    flow = await create_flow(client, draft_calling("https://api.example.com/x"))

    assert (await client.post(f"/flows/{flow['id']}/validate")).json() == {"valid": True}


@pytest.mark.parametrize(
    ("url", "code"),
    [
        ("https://localhost/x", "host_not_allowed"),
        ("http://api.example.com/x", "scheme_not_allowed"),
        ("https://", "invalid_url"),
    ],
)
async def test_validate_names_what_is_wrong_with_the_url(
    client: httpx.AsyncClient, restricted: OutboundPolicy, url: str, code: str
) -> None:
    flow = await create_flow(client, draft_calling(url))

    response = await client.post(f"/flows/{flow['id']}/validate")

    assert response.status_code == 422
    error = response.json()["details"]["errors"][0]
    assert (error["code"], error["node_id"], error["field"]) == (code, "call", "data.url")


async def test_a_default_server_validates_a_local_url(client: httpx.AsyncClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    try:
        flow = await create_flow(client, draft_calling("http://localhost:8000/health"))
        response = await client.post(f"/flows/{flow['id']}/validate")
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.json() == {"valid": True}


async def test_the_metadata_address_is_refused_even_by_a_default_server(
    client: httpx.AsyncClient,
) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    try:
        flow = await create_flow(client, draft_calling("http://169.254.169.254/latest/meta-data/"))
        response = await client.post(f"/flows/{flow['id']}/validate")
    finally:
        app.dependency_overrides.pop(get_settings, None)

    error = response.json()["details"]["errors"][0]
    assert (response.status_code, error["code"]) == (422, "blocked_destination")
