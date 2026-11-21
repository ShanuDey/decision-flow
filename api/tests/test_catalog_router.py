from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from cryptography.fernet import Fernet

from app.catalog.health import EntryHealth, HealthReport, HealthSource, get_health_source
from app.catalog.index import build_index
from app.catalog.remote import CatalogSource, get_catalog_source
from app.catalog.source import load_files
from app.main import app
from app.secrets.crypto import SecretBox, get_box, get_box_factory
from tests.auth_helpers import bearer
from tests.conftest import MARKETPLACE, FakeInstalledStore, create_flow
from tests.test_node_http_request import flow as http_flow
from tests.test_node_http_request import serve

pytestmark = pytest.mark.anyio

OTHER = bearer(sub="user-2")
TOKEN = "test-token"


@pytest.fixture
def box() -> Iterator[SecretBox]:
    secret_box = SecretBox([Fernet.generate_key().decode()])
    app.dependency_overrides[get_box] = lambda: secret_box
    app.dependency_overrides[get_box_factory] = lambda: lambda: secret_box
    yield secret_box
    app.dependency_overrides.pop(get_box, None)
    app.dependency_overrides.pop(get_box_factory, None)


async def entry(client: httpx.AsyncClient, kind: str, item_id: str) -> dict[str, Any]:
    items = (await client.get("/catalog/index")).json()["entries"]
    return next(e for e in items if (e["kind"], e["id"]) == (kind, item_id))


async def install(client: httpx.AsyncClient, kind: str, item_id: str, **changes: Any):
    found = await entry(client, kind, item_id)
    body = {"kind": kind, "id": item_id, "version": found["version"], "hash": found["hash"]}
    return await client.post("/catalog/install", json=body | changes)


async def type_ids(client: httpx.AsyncClient, headers: dict[str, str] | None = None) -> set[str]:
    items = (await client.get("/connection-types", headers=headers)).json()["items"]
    return {t["id"] for t in items}


async def test_the_index_is_the_one_the_source_serves(client: httpx.AsyncClient) -> None:
    body = (await client.get("/catalog/index")).json()
    expected = build_index(load_files(MARKETPLACE / "catalog")).model_dump(mode="json")
    entries = [
        {k: v for k, v in e.items() if k not in ("health", "health_reason")}
        for e in body["entries"]
    ]
    assert entries == expected["entries"] and body["stale"] is False
    assert {(e["health"], e["health_reason"]) for e in body["entries"]} == {("ok", "")}
    assert body["fetched_at"].endswith(("Z", "+00:00"))
    assert {(e["kind"], e["id"]) for e in body["entries"]} >= {
        ("connection-type", "github"),
        ("node-template", "github_create_issue"),
    }


async def test_nothing_is_installed_to_start_with(client: httpx.AsyncClient) -> None:
    assert (await client.get("/catalog/installed")).json() == {"items": []}
    assert "github" not in await type_ids(client)


async def test_installing_a_connection_type_makes_it_available_in_this_workspace_only(
    client: httpx.AsyncClient,
) -> None:
    response = await install(client, "connection-type", "github")
    assert response.status_code == 201
    first = response.json()["installed"][0]
    assert (first["kind"], first["id"], first["name"], first["version"]) == (
        "connection-type",
        "github",
        "GitHub",
        "1.0.0",
    )
    assert "github" in await type_ids(client)
    listed = (await client.get("/catalog/installed")).json()["items"]
    assert [i["id"] for i in listed] == ["github"]

    assert "github" not in await type_ids(client, OTHER)
    assert (await client.get("/catalog/installed", headers=OTHER)).json() == {"items": []}


async def test_an_installed_type_is_marked_as_installed_in_the_type_list(
    client: httpx.AsyncClient,
) -> None:
    await install(client, "connection-type", "github")
    items = {t["id"]: t for t in (await client.get("/connection-types")).json()["items"]}
    assert items["github"]["source"] == "installed" and items["github"]["hosts"] == [
        "api.github.com"
    ]
    assert items["bearer"]["source"] == "builtin"
    order = [t["id"] for t in (await client.get("/connection-types")).json()["items"]]
    assert order.index("github") > order.index("bearer")


async def test_installing_a_template_also_installs_the_type_it_needs(
    client: httpx.AsyncClient,
) -> None:
    response = await install(client, "node-template", "github_create_issue")
    assert response.status_code == 201
    assert [(i["kind"], i["id"]) for i in response.json()["installed"]] == [
        ("node-template", "github_create_issue"),
        ("connection-type", "github"),
    ]
    assert "github" in await type_ids(client)

    items = (await client.get("/node-templates")).json()["items"]
    sources = {i["template"]["id"]: i["source"] for i in items}
    assert sources["github_create_issue"] == "installed"
    assert sources["openai_compatible_chat_completion"] == "builtin"


async def test_a_second_install_of_the_same_item_changes_nothing_else(
    client: httpx.AsyncClient, installed_store: FakeInstalledStore
) -> None:
    await install(client, "node-template", "github_create_issue")
    again = await install(client, "node-template", "github_create_issue")
    assert again.status_code == 201
    assert [i["id"] for i in again.json()["installed"]] == ["github_create_issue"]
    assert len(installed_store.rows) == 2


async def test_a_changed_entry_is_refused_before_anything_is_stored(
    client: httpx.AsyncClient,
) -> None:
    response = await install(client, "connection-type", "github", hash="sha256-" + "0" * 64)
    assert response.status_code == 409 and response.json()["code"] == "hash_mismatch"
    assert (await client.get("/catalog/installed")).json() == {"items": []}


async def test_an_entry_that_does_not_exist_is_404(client: httpx.AsyncClient) -> None:
    found = await entry(client, "connection-type", "github")
    body = {"kind": "connection-type", "id": "nope", "version": "1.0.0", "hash": found["hash"]}
    response = await client.post("/catalog/install", json=body)
    assert response.status_code == 404 and response.json()["code"] == "catalog_item_not_found"


async def test_a_version_that_is_no_longer_current_asks_for_a_refresh(
    client: httpx.AsyncClient,
) -> None:
    found = await entry(client, "connection-type", "github")
    body = {"kind": "connection-type", "id": "github", "version": "9.9.9", "hash": found["hash"]}
    response = await client.post("/catalog/install", json=body)
    assert response.status_code == 409 and response.json()["code"] == "hash_mismatch"


async def test_a_built_in_item_cannot_be_installed(client: httpx.AsyncClient) -> None:
    body = {"kind": "connection-type", "id": "bearer", "version": "1.0.0", "hash": "x"}
    assert (await client.post("/catalog/install", json=body)).status_code == 404


@pytest.mark.usefixtures("box")
async def test_a_connection_of_an_installed_type_can_be_made_and_listed(
    client: httpx.AsyncClient,
) -> None:
    body = {"type": "github", "name": "GitHub", "values": {"token": TOKEN}}
    assert (await client.post("/connections", json=body)).status_code == 422

    await install(client, "connection-type", "github")
    made = await client.post("/connections", json=body)
    assert made.status_code == 201 and made.json()["type"] == "github"
    listed = (await client.get("/connections")).json()["items"]
    assert [(c["type"], c["secrets_set"]) for c in listed] == [("github", ["token"])]
    assert TOKEN not in made.text


@pytest.mark.usefixtures("box")
async def test_a_run_uses_an_installed_type_and_its_fixed_host(client: httpx.AsyncClient) -> None:
    await install(client, "connection-type", "github")
    body = {"type": "github", "name": "GitHub", "values": {"token": TOKEN}}
    made = (await client.post("/connections", json=body)).json()
    async with serve() as (port, received):
        call = {"url": f"http://127.0.0.1:{port}/echo", "connection_id": made["id"]}
        flow = await create_flow(client, http_flow(call))
        run = await client.post(f"/flows/{flow['id']}/runs", json={"test": True, "input": {}})

    assert run.json()["status"] == "failed" and received == []
    assert "may only call api.github.com" in run.json()["error"]["message"]
    assert TOKEN not in run.text


@pytest.mark.usefixtures("box")
async def test_a_type_with_connections_cannot_be_uninstalled(client: httpx.AsyncClient) -> None:
    await install(client, "connection-type", "github")
    body = {"type": "github", "name": "GitHub", "values": {"token": TOKEN}}
    made = (await client.post("/connections", json=body)).json()

    blocked = await client.delete("/catalog/installed/connection-type/github")
    assert blocked.status_code == 409 and blocked.json()["code"] == "type_in_use"
    assert blocked.json()["details"]["count"] == 1

    await client.delete(f"/connections/{made['id']}")
    assert (await client.delete("/catalog/installed/connection-type/github")).status_code == 204
    assert "github" not in await type_ids(client)


async def test_a_type_an_installed_template_needs_cannot_be_uninstalled(
    client: httpx.AsyncClient,
) -> None:
    await install(client, "node-template", "github_create_issue")
    blocked = await client.delete("/catalog/installed/connection-type/github")
    assert blocked.status_code == 409 and blocked.json()["code"] == "required_by"
    assert blocked.json()["details"]["names"] == ["GitHub: create issue"]

    assert (
        await client.delete("/catalog/installed/node-template/github_create_issue")
    ).status_code == 204
    assert (await client.delete("/catalog/installed/connection-type/github")).status_code == 204


async def test_uninstalling_something_not_installed_or_from_another_workspace_is_404(
    client: httpx.AsyncClient,
) -> None:
    assert (await client.delete("/catalog/installed/node-template/nope")).status_code == 404
    await install(client, "connection-type", "github")
    other = await client.delete("/catalog/installed/connection-type/github", headers=OTHER)
    assert other.status_code == 404
    assert "github" in await type_ids(client)


async def test_a_template_removed_from_the_workspace_leaves_the_node_it_filled_alone(
    client: httpx.AsyncClient,
) -> None:
    await install(client, "node-template", "slack_post_message")
    await client.delete("/catalog/installed/node-template/slack_post_message")
    items = (await client.get("/node-templates")).json()["items"]
    assert "slack_post_message" not in {i["template"]["id"] for i in items}


async def test_the_routes_need_a_sign_in(anon_client: httpx.AsyncClient) -> None:
    assert (await anon_client.get("/catalog/index")).status_code == 401
    assert (await anon_client.get("/catalog/installed")).status_code == 401
    body = {"kind": "connection-type", "id": "github", "version": "1.0.0", "hash": "x"}
    assert (await anon_client.post("/catalog/install", json=body)).status_code == 401
    assert (
        await anon_client.delete("/catalog/installed/connection-type/github")
    ).status_code == 401


async def test_a_catalog_that_cannot_be_read_is_503_but_installed_items_still_work(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    await install(client, "connection-type", "github")
    app.dependency_overrides[get_catalog_source] = lambda: CatalogSource(str(tmp_path / "missing"))
    index = await client.get("/catalog/index")
    assert index.status_code == 503 and index.json()["code"] == "catalog_unavailable"
    body = {"kind": "connection-type", "id": "slack", "version": "1.0.0", "hash": "x"}
    assert (await client.post("/catalog/install", json=body)).status_code == 503
    assert (await client.post("/catalog/refresh")).status_code == 503

    assert [i["id"] for i in (await client.get("/catalog/installed")).json()["items"]] == ["github"]
    assert "github" in await type_ids(client)
    assert (await client.get("/node-templates")).status_code == 200


async def test_an_empty_catalog_url_switches_the_marketplace_off(
    client: httpx.AsyncClient,
) -> None:
    app.dependency_overrides[get_catalog_source] = lambda: CatalogSource("")
    response = await client.get("/catalog/index")
    assert response.status_code == 503 and response.json()["details"] == {"disabled": True}
    assert (await client.get("/catalog/installed")).status_code == 200
    assert "bearer" in await type_ids(client)


async def test_refresh_returns_the_index(client: httpx.AsyncClient) -> None:
    body = (await client.post("/catalog/refresh")).json()
    assert {e["id"] for e in body["entries"]} >= {"github", "slack"}


async def test_a_readme_is_served_as_markdown(client: httpx.AsyncClient) -> None:
    response = await client.get("/catalog/readme/connection-type/github")
    expected = (MARKETPLACE / "catalog/connection-types/github/README.md").read_text("utf-8")
    assert response.status_code == 200
    assert response.json()["markdown"].replace("\r\n", "\n") == expected.replace("\r\n", "\n")


async def test_an_item_with_no_readme_is_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/catalog/readme/connection-type/nope")
    assert response.status_code == 404 and response.json()["code"] == "catalog_item_not_found"


async def test_a_built_in_item_has_no_readme_page(client: httpx.AsyncClient) -> None:
    assert (await client.get("/catalog/readme/connection-type/bearer")).status_code == 404


async def test_a_readme_kind_must_be_a_known_kind(client: httpx.AsyncClient) -> None:
    assert (await client.get("/catalog/readme/flow/github")).status_code == 422


def report_source(entries: dict[str, EntryHealth]) -> HealthSource:
    source = HealthSource("https://health.test")
    source._report = HealthReport(generated_at=datetime.now(UTC), entries=entries)
    source._attempted = float("inf")
    return source


def broken(reason: str = "file no longer valid") -> EntryHealth:
    return EntryHealth(status="broken", failures=2, checked_at=datetime.now(UTC), reason=reason)


def use_health(source: HealthSource) -> None:
    app.dependency_overrides[get_health_source] = lambda: source


@pytest.fixture
async def broken_github(client: httpx.AsyncClient) -> AsyncIterator[None]:
    # After `client`, which installs its own empty health source.
    use_health(report_source({"connection-type/github": broken()}))
    yield
    app.dependency_overrides.pop(get_health_source, None)


@pytest.mark.usefixtures("broken_github")
async def test_a_broken_item_is_marked_in_the_listing(client: httpx.AsyncClient) -> None:
    found = await entry(client, "connection-type", "github")
    assert (found["health"], found["health_reason"]) == ("broken", "file no longer valid")
    assert (await entry(client, "connection-type", "slack"))["health"] == "ok"


@pytest.mark.usefixtures("broken_github")
async def test_a_broken_item_cannot_be_installed(client: httpx.AsyncClient) -> None:
    response = await install(client, "connection-type", "github")
    assert response.status_code == 409 and response.json()["code"] == "catalog_item_broken"
    assert "file no longer valid" in response.json()["message"]
    assert (await client.get("/catalog/installed")).json() == {"items": []}


@pytest.mark.usefixtures("broken_github")
async def test_a_template_needing_a_broken_type_cannot_be_installed(
    client: httpx.AsyncClient,
) -> None:
    response = await install(client, "node-template", "github_create_issue")
    assert response.status_code == 409 and response.json()["code"] == "catalog_item_broken"
    assert (await client.get("/catalog/installed")).json() == {"items": []}


@pytest.mark.usefixtures("broken_github")
async def test_a_broken_type_that_is_already_installed_does_not_block_its_template(
    client: httpx.AsyncClient,
) -> None:
    use_health(HealthSource(""))
    assert (await install(client, "connection-type", "github")).status_code == 201
    use_health(report_source({"connection-type/github": broken()}))
    assert (await install(client, "node-template", "github_create_issue")).status_code == 201


@pytest.mark.usefixtures("broken_github")
async def test_a_healthy_item_installs_while_another_is_broken(client: httpx.AsyncClient) -> None:
    assert (await install(client, "connection-type", "slack")).status_code == 201
