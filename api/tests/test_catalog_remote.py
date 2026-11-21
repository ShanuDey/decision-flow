import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.catalog.remote import (
    MAX_FILE_BYTES,
    TTL_SECONDS,
    CatalogItemInvalid,
    CatalogItemMissing,
    CatalogSource,
    CatalogUnavailable,
    get_catalog_source,
)
from app.main import app
from tests.conftest import MARKETPLACE

pytestmark = pytest.mark.anyio

BASE = "https://catalog.test/marketplace"
KEY = {"kind": "connection-type", "id": "github", "version": "1.0.0"}


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class Remote:
    """A fake host serving the real marketplace folder, with hooks to break it."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {
            path.relative_to(MARKETPLACE).as_posix(): path.read_bytes()
            for path in MARKETPLACE.rglob("*.json")
            if "schemas" not in path.parts
        }
        self.requests: list[str] = []
        self.respond: Callable[[httpx.Request], httpx.Response] | None = None
        self.down = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request.url.path)
        if self.down:
            raise httpx.ConnectError("down")
        if self.respond is not None:
            return self.respond(request)
        name = request.url.path.removeprefix("/marketplace/")
        if name in self.files:
            return httpx.Response(200, content=self.files[name])
        return httpx.Response(404)

    def source(self, clock: Callable[[], float] | None = None) -> CatalogSource:
        transport = httpx.MockTransport(self.handler)
        return CatalogSource(BASE, transport=transport, **({"clock": clock} if clock else {}))


def use(remote: Remote) -> None:
    source = remote.source()
    app.dependency_overrides[get_catalog_source] = lambda: source


@pytest.fixture
def remote() -> Remote:
    return Remote()


def entry_of(listing_entries: list[Any], kind: str, item_id: str) -> Any:
    return next(e for e in listing_entries if (e.kind, e.id) == (kind, item_id))


async def test_the_index_is_fetched_validated_and_stamped(remote: Remote) -> None:
    listing = await remote.source().index()
    assert remote.requests == ["/marketplace/index.json"]
    assert {e.id for e in listing.index.entries} >= {"github", "slack"}
    assert listing.stale is False and listing.fetched_at.tzinfo is not None


async def test_a_second_call_inside_the_ttl_uses_the_cache(remote: Remote) -> None:
    clock = Clock()
    source = remote.source(clock)
    first = await source.index()
    clock.now += TTL_SECONDS - 1
    second = await source.index()
    assert remote.requests == ["/marketplace/index.json"]
    assert second.fetched_at == first.fetched_at


async def test_the_index_is_fetched_again_after_the_ttl(remote: Remote) -> None:
    clock = Clock()
    source = remote.source(clock)
    await source.index()
    clock.now += TTL_SECONDS + 1
    await source.index()
    assert remote.requests == ["/marketplace/index.json"] * 2


async def test_a_failed_refresh_serves_the_previous_copy_marked_stale(remote: Remote) -> None:
    clock = Clock()
    source = remote.source(clock)
    first = await source.index()
    clock.now += TTL_SECONDS + 1
    remote.down = True
    again = await source.index()
    assert again.stale is True and again.index == first.index
    assert again.fetched_at == first.fetched_at

    remote.down = False
    clock.now += 31
    recovered = await source.index()
    assert (
        recovered.stale is False
        and recovered.fetched_at >= first.fetched_at
        and len(remote.requests) == 3
    )


async def test_a_stale_copy_is_not_retried_on_every_call(remote: Remote) -> None:
    clock = Clock()
    source = remote.source(clock)
    await source.index()
    clock.now += TTL_SECONDS + 1
    remote.down = True
    await source.index()
    await source.index()
    assert len(remote.requests) == 2


async def test_force_refreshes_but_not_more_than_once_in_thirty_seconds(remote: Remote) -> None:
    clock = Clock()
    source = remote.source(clock)
    await source.index()
    clock.now += 5
    await source.index(force=True)
    assert len(remote.requests) == 1
    clock.now += 30
    await source.index(force=True)
    assert len(remote.requests) == 2


async def test_an_unreachable_catalog_with_nothing_cached_is_unavailable(remote: Remote) -> None:
    remote.down = True
    with pytest.raises(CatalogUnavailable):
        await remote.source().index()


@pytest.mark.parametrize("content", [b"{", b"[]", b'{"entries": [{"id": 1}]}'])
async def test_an_index_that_is_not_valid_is_unavailable(remote: Remote, content: bytes) -> None:
    remote.files["index.json"] = content
    with pytest.raises(CatalogUnavailable, match="not valid"):
        await remote.source().index()


async def test_a_redirect_is_refused(remote: Remote) -> None:
    remote.respond = lambda _: httpx.Response(302, headers={"location": "https://evil.test/x"})
    with pytest.raises(CatalogUnavailable):
        await remote.source().index()
    assert remote.requests == ["/marketplace/index.json"]


async def test_plain_http_is_refused() -> None:
    called: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        called.append(str(request.url))
        return httpx.Response(200)

    source = CatalogSource("http://catalog.test", transport=httpx.MockTransport(handler))
    with pytest.raises(CatalogUnavailable, match="https"):
        await source.index()
    assert called == []


async def test_a_file_is_read_from_a_path_built_from_its_parts(remote: Remote) -> None:
    source = remote.source()
    file = await source.read("node-template", "github_create_issue", "1.0.0")
    assert (file.id, file.version) == ("github_create_issue", "1.0.0")
    assert remote.requests == [
        "/marketplace/index.json",
        "/marketplace/catalog/node-templates/github_create_issue/1.0.0.json",
    ]


async def test_a_file_over_the_size_cap_is_refused(remote: Remote) -> None:
    key = "catalog/connection-types/github/1.0.0.json"
    remote.files[key] = b" " * (MAX_FILE_BYTES + 1)
    with pytest.raises(CatalogUnavailable, match="too large"):
        await remote.source().read("connection-type", "github", "1.0.0")


@pytest.mark.parametrize(
    ("item_id", "version"),
    [
        ("../../etc/passwd", "1.0.0"),
        ("github/../slack", "1.0.0"),
        ("github", "1.0.0/../../x"),
        ("GitHub", "1.0.0"),
        ("github", "1.0"),
        ("github%2F..", "1.0.0"),
        ("", "1.0.0"),
    ],
)
async def test_an_id_or_version_that_is_not_plain_never_reaches_the_network(
    remote: Remote, item_id: str, version: str
) -> None:
    with pytest.raises(CatalogItemMissing):
        await remote.source().read("connection-type", item_id, version)
    assert remote.requests == []


async def test_a_missing_file_is_not_found(remote: Remote) -> None:
    with pytest.raises(CatalogItemMissing):
        await remote.source().read("connection-type", "github", "9.9.9")


async def test_a_file_whose_id_does_not_match_its_path_is_invalid(remote: Remote) -> None:
    key = "catalog/connection-types/github/1.0.0.json"
    body = json.loads(remote.files[key])
    remote.files[key] = json.dumps(body | {"id": "slack"}).encode()
    with pytest.raises(CatalogItemInvalid, match="do not match"):
        await remote.source().read("connection-type", "github", "1.0.0")


async def test_a_file_that_fails_the_models_is_invalid(remote: Remote) -> None:
    key = "catalog/connection-types/github/1.0.0.json"
    remote.files[key] = json.dumps({"id": "github"}).encode()
    with pytest.raises(CatalogItemInvalid):
        await remote.source().read("connection-type", "github", "1.0.0")


async def test_a_template_needs_a_connection_type_from_the_built_ins_or_the_index(
    remote: Remote,
) -> None:
    key = "catalog/node-templates/slack_post_message/1.0.0.json"
    body = json.loads(remote.files[key])
    body["connection"]["type"] = "ghost"
    remote.files[key] = json.dumps(body).encode()
    with pytest.raises(CatalogItemInvalid, match="does not exist"):
        await remote.source().read("node-template", "slack_post_message", "1.0.0")


async def test_a_local_folder_works_like_a_remote_one() -> None:
    source = CatalogSource(str(MARKETPLACE))
    listing = await source.index()
    assert {e.id for e in listing.index.entries} >= {"github", "slack"}
    assert (await source.read("connection-type", "github", "1.0.0")).id == "github"
    with pytest.raises(CatalogItemMissing):
        await source.read("connection-type", "github", "9.9.9")


async def test_a_local_folder_without_an_index_is_unavailable(tmp_path: Path) -> None:
    with pytest.raises(CatalogUnavailable):
        await CatalogSource(str(tmp_path)).index()


async def test_an_empty_url_is_switched_off() -> None:
    with pytest.raises(CatalogUnavailable) as raised:
        await CatalogSource("").index()
    assert raised.value.disabled is True


async def test_the_default_setting_points_at_the_public_repo() -> None:
    from app.settings import Settings

    assert Settings(_env_file=None).catalog_url.startswith("https://raw.githubusercontent.com/")


async def test_the_app_serves_built_ins_with_no_marketplace_folder(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    app.dependency_overrides[get_catalog_source] = lambda: CatalogSource(str(tmp_path / "nope"))
    types = (await client.get("/connection-types")).json()["items"]
    assert "bearer" in {t["id"] for t in types}
    templates = (await client.get("/node-templates")).json()["items"]
    assert templates
    assert (await client.get("/catalog/installed")).status_code == 200


async def test_install_through_the_api_checks_the_file_against_the_entry_hash(
    client: httpx.AsyncClient, remote: Remote
) -> None:
    use(remote)
    entries = (await client.get("/catalog/index")).json()["entries"]
    github = next(e for e in entries if e["id"] == "github" and e["kind"] == "connection-type")
    key = "catalog/connection-types/github/1.0.0.json"
    body = json.loads(remote.files[key])
    remote.files[key] = json.dumps(body | {"description": "Changed after the index."}).encode()

    request = {
        "kind": "connection-type",
        "id": "github",
        "version": "1.0.0",
        "hash": github["hash"],
    }
    response = await client.post("/catalog/install", json=request)
    assert response.status_code == 409 and response.json()["code"] == "hash_mismatch"
    assert (await client.get("/catalog/installed")).json() == {"items": []}


async def test_a_requirement_the_index_does_not_list_is_refused(
    client: httpx.AsyncClient, remote: Remote
) -> None:
    index = json.loads(remote.files["index.json"])
    index["entries"] = [
        e for e in index["entries"] if (e["kind"], e["id"]) != ("connection-type", "github")
    ]
    remote.files["index.json"] = json.dumps(index).encode()
    use(remote)
    entries = (await client.get("/catalog/index")).json()["entries"]
    template = next(e for e in entries if e["id"] == "github_create_issue")
    request = {
        "kind": "node-template",
        "id": "github_create_issue",
        "version": "1.0.0",
        "hash": template["hash"],
    }
    response = await client.post("/catalog/install", json=request)
    assert response.status_code == 409 and response.json()["code"] == "requirement_missing"


async def test_install_fetches_one_file_per_item(client: httpx.AsyncClient, remote: Remote) -> None:
    use(remote)
    entries = (await client.get("/catalog/index")).json()["entries"]
    slack = next(e for e in entries if e["id"] == "slack")
    request = {"kind": "connection-type", "id": "slack", "version": "1.0.0", "hash": slack["hash"]}
    assert (await client.post("/catalog/install", json=request)).status_code == 201
    assert remote.requests == [
        "/marketplace/index.json",
        "/marketplace/catalog/connection-types/slack/1.0.0.json",
    ]


async def test_a_traversal_id_in_an_install_request_is_404_and_fetches_nothing(
    client: httpx.AsyncClient, remote: Remote
) -> None:
    use(remote)
    request = {"kind": "connection-type", "id": "../index", "version": "1.0.0", "hash": "x"}
    response = await client.post("/catalog/install", json=request)
    assert response.status_code == 404
    assert all("index.json" in p for p in remote.requests)


async def test_an_unreachable_remote_is_503_from_the_routes(
    client: httpx.AsyncClient, remote: Remote
) -> None:
    remote.down = True
    use(remote)
    response = await client.get("/catalog/index")
    assert response.status_code == 503 and response.json()["code"] == "catalog_unavailable"


async def test_a_failed_first_fetch_is_not_retried_inside_the_refresh_window(
    remote: Remote,
) -> None:
    clock = Clock()
    source = remote.source(clock)
    remote.down = True
    for _ in range(3):
        with pytest.raises(CatalogUnavailable):
            await source.index()
    assert len(remote.requests) == 1
    clock.now += 31
    remote.down = False
    assert (await source.index()).stale is False


async def test_an_index_from_a_newer_catalog_still_lists_what_this_app_can_read(
    remote: Remote,
) -> None:
    document = json.loads(remote.files["index.json"])
    document["entries"][0]["added_later"] = True
    document["entries"].append({"id": "odd", "kind": "something-new"})
    remote.files["index.json"] = json.dumps(document).encode()
    listing = await remote.source().index()
    assert len(listing.index.entries) == len(document["entries"]) - 1


async def test_an_index_with_another_schema_version_is_unavailable(remote: Remote) -> None:
    document = json.loads(remote.files["index.json"]) | {"schema_version": 2}
    remote.files["index.json"] = json.dumps(document).encode()
    with pytest.raises(CatalogUnavailable, match="not valid"):
        await remote.source().index()
