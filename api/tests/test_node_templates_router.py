from collections.abc import Iterator

import httpx
import pytest

from app.limits import Limits, get_limits
from app.main import app
from app.node_templates.catalog import TEMPLATES
from app.settings import Settings, get_settings

pytestmark = pytest.mark.anyio


@pytest.fixture
def http_off() -> Iterator[None]:
    app.dependency_overrides[get_limits] = lambda: Limits(
        _env_file=None, disabled_node_types=["http_request"]
    )
    yield
    app.dependency_overrides.pop(get_limits, None)


async def test_the_list_returns_every_template_with_its_full_settings(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/node-templates")
    assert response.status_code == 200
    items = response.json()["items"]
    assert [i["id"] for i in items] == [t.id for t in TEMPLATES]
    issue = next(i for i in items if i["id"] == "github_create_issue")
    assert issue["connection"] == {"type": "bearer", "values": {"hosts": "api.github.com"}}
    assert issue["data"]["method"] == "POST" and issue["data"]["connection_id"] == ""
    assert issue["data"]["headers"]["Accept"] == "application/vnd.github+json"


async def test_it_can_be_filtered_by_node_type(client: httpx.AsyncClient) -> None:
    both = (await client.get("/node-templates?node_type=http_request")).json()["items"]
    assert len(both) == len(TEMPLATES)
    assert (await client.get("/node-templates?node_type=subflow")).status_code == 422


@pytest.mark.usefixtures("http_off")
async def test_a_server_that_turns_the_node_off_offers_no_templates(
    client: httpx.AsyncClient,
) -> None:
    assert (await client.get("/node-templates")).json() == {"items": []}


async def test_it_needs_a_sign_in(anon_client: httpx.AsyncClient) -> None:
    assert (await anon_client.get("/node-templates")).status_code == 401


@pytest.fixture
def only_github() -> Iterator[None]:
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, http_allowed_hosts=["api.github.com"]
    )
    yield
    app.dependency_overrides.pop(get_settings, None)


@pytest.mark.usefixtures("only_github")
async def test_a_server_with_an_allowed_host_list_offers_only_templates_it_could_run(
    client: httpx.AsyncClient,
) -> None:
    items = (await client.get("/node-templates")).json()["items"]
    assert [i["id"] for i in items] == ["github_create_issue"]


async def test_a_server_that_requires_https_keeps_templates_that_already_use_it(
    client: httpx.AsyncClient,
) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, allow_private_networks=False
    )
    try:
        items = (await client.get("/node-templates")).json()["items"]
    finally:
        app.dependency_overrides.pop(get_settings, None)
    assert [i["id"] for i in items] == [t.id for t in TEMPLATES]
