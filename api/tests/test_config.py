from collections.abc import Iterator

import httpx
import pytest

from app.limits import Limits, get_limits
from app.main import app

pytestmark = pytest.mark.anyio

# Every field here is public to any signed-in user: add one only on purpose.
PUBLIC_FIELDS = {
    "delete_mode",
    "disabled_node_types",
    "max_nodes",
    "max_edges",
    "limit_notice",
    "limit_notice_url",
}


@pytest.fixture
def limits() -> Iterator[None]:
    app.dependency_overrides[get_limits] = lambda: Limits(_env_file=None)
    yield
    app.dependency_overrides.pop(get_limits, None)


@pytest.mark.usefixtures("limits")
async def test_config_lists_exactly_the_public_fields(client: httpx.AsyncClient) -> None:
    assert set((await client.get("/config")).json()) == PUBLIC_FIELDS


@pytest.mark.usefixtures("limits")
async def test_config_reports_the_defaults(client: httpx.AsyncClient) -> None:
    body = (await client.get("/config")).json()
    assert body["disabled_node_types"] == []
    assert (body["max_nodes"], body["max_edges"]) == (500, 1000)
    assert (body["limit_notice"], body["limit_notice_url"]) == ("", "")


async def test_config_reports_the_operators_limits(client: httpx.AsyncClient) -> None:
    app.dependency_overrides[get_limits] = lambda: Limits(
        _env_file=None,
        disabled_node_types="http_request, subflow",
        max_nodes=50,
        max_edges=0,
        limit_notice="Free demo",
        limit_notice_url="https://example.com/plans",
    )
    try:
        body = (await client.get("/config")).json()
    finally:
        app.dependency_overrides.pop(get_limits, None)
    assert body["disabled_node_types"] == ["http_request", "subflow"]
    assert (body["max_nodes"], body["max_edges"]) == (50, 0)
    assert body["limit_notice"] == "Free demo"
    assert body["limit_notice_url"] == "https://example.com/plans"


async def test_config_needs_a_signed_in_user(anon_client: httpx.AsyncClient) -> None:
    assert (await anon_client.get("/config")).status_code == 401
