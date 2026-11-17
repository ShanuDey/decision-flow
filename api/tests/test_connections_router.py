import uuid
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from cryptography.fernet import Fernet

from app.connections.catalog import BY_ID
from app.limits import Limits, get_limits
from app.main import app
from app.secrets.crypto import SecretBox, get_box, get_box_factory
from tests.auth_helpers import bearer
from tests.conftest import FakeConnectionStore, create_flow, service_type
from tests.test_node_http_request import flow as http_flow
from tests.test_node_http_request import serve
from tests.test_node_subflow import parent_draft, publish

pytestmark = pytest.mark.anyio

KEY = "sk-test-key-1234567890"
OTHER = bearer(sub="user-2")


@pytest.fixture
def with_service(monkeypatch: pytest.MonkeyPatch):
    def add(**changes: Any) -> None:
        monkeypatch.setitem(BY_ID, "acme", service_type(**changes))

    return add


@pytest.fixture
def box() -> Iterator[SecretBox]:
    secret_box = SecretBox([Fernet.generate_key().decode()])
    app.dependency_overrides[get_box] = lambda: secret_box
    app.dependency_overrides[get_box_factory] = lambda: lambda: secret_box
    yield secret_box
    app.dependency_overrides.pop(get_box, None)
    app.dependency_overrides.pop(get_box_factory, None)


def bearer_body(name: str = "Billing API", **values: str) -> dict[str, Any]:
    fields = {"token": KEY, "hosts": "api.example.com"} | values
    return {"type": "bearer", "name": name, "values": fields}


@pytest.mark.usefixtures("box")
async def test_the_types_list_describes_each_field_and_pinned_hosts(
    client: httpx.AsyncClient,
) -> None:
    items = {t["id"]: t for t in (await client.get("/connection-types")).json()["items"]}
    assert set(items) == {"openai_compatible", "bearer", "basic", "api_key_header"}
    assert (
        items["openai_compatible"]["category"] == "builtin"
        and items["bearer"]["category"] == "custom"
    )
    assert (
        items["openai_compatible"]["hosts_from"] == "base_url"
        and items["openai_compatible"]["testable"] is True
    )
    base = next(f for f in items["openai_compatible"]["fields"] if f["name"] == "base_url")
    assert (base["format"], base["default"], base["required"]) == (
        "url",
        "https://api.openai.com/v1",
        True,
    )
    assert items["bearer"]["hosts"] == []
    assert items["bearer"]["testable"] is False and items["bearer"]["hosts_from"] == ""
    token = next(f for f in items["bearer"]["fields"] if f["name"] == "token")
    assert token["secret"] is True


@pytest.mark.usefixtures("box")
async def test_create_then_list_never_returns_the_secret(client: httpx.AsyncClient) -> None:
    created = await client.post("/connections", json=bearer_body())
    assert created.status_code == 201
    body = created.json()
    assert body["type"] == "bearer" and body["config"] == {"hosts": "api.example.com"}
    assert body["secrets_set"] == ["token"]
    listed = await client.get("/connections")
    assert [c["name"] for c in listed.json()["items"]] == ["Billing API"]
    assert KEY not in created.text and KEY not in listed.text


async def test_the_secret_is_stored_encrypted(
    client: httpx.AsyncClient, box: SecretBox, connection_store: FakeConnectionStore
) -> None:
    await client.post("/connections", json=bearer_body())
    (row,) = connection_store.rows.values()
    assert KEY not in row.secrets_encrypted and KEY not in str(row.config)
    assert KEY in box.decrypt(row.secrets_encrypted)


@pytest.mark.usefixtures("box")
@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"type": "nope", "name": "x", "values": {}}, None),
        (bearer_body(token=""), "token"),
        (bearer_body(token="short"), "token"),
        (bearer_body(hosts=""), "hosts"),
        (bearer_body(hosts="https://api.example.com/v1"), "hosts"),
        (bearer_body(hosts="a.com," * 11), "hosts"),
        (bearer_body(x="y"), "x"),
    ],
)
async def test_bad_values_are_refused(
    client: httpx.AsyncClient, body: dict[str, Any], field: str | None
) -> None:
    response = await client.post("/connections", json=body)
    assert response.status_code == 422
    if field:
        assert response.json()["code"] == "invalid_connection"
        assert response.json()["details"]["field"] == field


@pytest.mark.usefixtures("box")
async def test_a_fixed_host_type_needs_no_hosts_field(
    client: httpx.AsyncClient, with_service
) -> None:
    with_service()
    response = await client.post(
        "/connections", json={"type": "acme", "name": "Acme", "values": {"api_key": KEY}}
    )
    assert response.status_code == 201
    assert response.json()["config"] == {}


@pytest.mark.usefixtures("box")
async def test_a_name_is_unique_per_workspace(client: httpx.AsyncClient) -> None:
    await client.post("/connections", json=bearer_body())
    again = await client.post("/connections", json=bearer_body())
    assert again.status_code == 409 and again.json()["code"] == "connection_name_taken"
    other = await client.post("/connections", json=bearer_body(), headers=OTHER)
    assert other.status_code == 201


async def test_update_keeps_a_secret_you_leave_out(
    client: httpx.AsyncClient, box: SecretBox, connection_store: FakeConnectionStore
) -> None:
    made = (await client.post("/connections", json=bearer_body())).json()
    patched = await client.patch(
        f"/connections/{made['id']}",
        json={"name": "Renamed", "values": {"hosts": "b.example.com"}},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Renamed"
    assert patched.json()["config"] == {"hosts": "b.example.com"}
    (row,) = connection_store.rows.values()
    assert KEY in box.decrypt(row.secrets_encrypted)


async def test_update_can_replace_the_secret(
    client: httpx.AsyncClient, box: SecretBox, connection_store: FakeConnectionStore
) -> None:
    made = (await client.post("/connections", json=bearer_body())).json()
    await client.patch(f"/connections/{made['id']}", json={"values": {"token": "another-key-9876"}})
    (row,) = connection_store.rows.values()
    assert "another-key-9876" in box.decrypt(row.secrets_encrypted)


@pytest.mark.usefixtures("box")
async def test_update_cannot_clear_a_required_field(client: httpx.AsyncClient) -> None:
    made = (await client.post("/connections", json=bearer_body())).json()
    response = await client.patch(f"/connections/{made['id']}", json={"values": {"hosts": ""}})
    assert response.status_code == 422


@pytest.mark.usefixtures("box")
async def test_another_workspace_sees_and_changes_nothing(client: httpx.AsyncClient) -> None:
    made = (await client.post("/connections", json=bearer_body())).json()
    assert (await client.get("/connections", headers=OTHER)).json() == {"items": []}
    patched = await client.patch(f"/connections/{made['id']}", json={"name": "x"}, headers=OTHER)
    assert patched.status_code == 404
    assert (await client.delete(f"/connections/{made['id']}", headers=OTHER)).status_code == 404
    assert len((await client.get("/connections")).json()["items"]) == 1


@pytest.mark.usefixtures("box")
async def test_delete_removes_it_and_a_second_delete_is_404(client: httpx.AsyncClient) -> None:
    made = (await client.post("/connections", json=bearer_body())).json()
    assert (await client.delete(f"/connections/{made['id']}")).status_code == 204
    assert (await client.delete(f"/connections/{made['id']}")).status_code == 404


def draft_using(connection_id: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "variables": [],
        "nodes": [
            {
                "id": "call",
                "type": "http_request",
                "name": "Call",
                "position": {"x": 0, "y": 0},
                "data": {"url": "https://api.example.com", "connection_id": connection_id},
            }
        ],
        "edges": [],
    }


@pytest.mark.usefixtures("box")
async def test_deleting_a_connection_a_flow_uses_is_refused_unless_forced(
    client: httpx.AsyncClient,
) -> None:
    made = (await client.post("/connections", json=bearer_body())).json()
    flow = await create_flow(client, draft_using(made["id"]))
    refused = await client.delete(f"/connections/{made['id']}")
    assert refused.status_code == 409
    assert refused.json()["code"] == "connection_in_use"
    assert refused.json()["details"]["flows"] == [{"id": flow["id"], "name": "Demo"}]
    assert (await client.delete(f"/connections/{made['id']}?force=true")).status_code == 204


@pytest.mark.usefixtures("box")
async def test_a_connection_nothing_uses_deletes_without_force(client: httpx.AsyncClient) -> None:
    made = (await client.post("/connections", json=bearer_body())).json()
    await create_flow(client, draft_using("00000000-0000-4000-8000-000000000000"))
    assert (await client.delete(f"/connections/{made['id']}")).status_code == 204


async def test_the_routes_need_a_sign_in(anon_client: httpx.AsyncClient) -> None:
    assert (await anon_client.get("/connections")).status_code == 401
    assert (await anon_client.post("/connections", json=bearer_body())).status_code == 401


@pytest.mark.usefixtures("box")
async def test_a_run_sends_the_connection_and_the_response_never_holds_the_key(
    client: httpx.AsyncClient,
) -> None:
    body = bearer_body(hosts="127.0.0.1")
    made = (await client.post("/connections", json=body)).json()
    async with serve() as (port, received):
        call = {"url": f"http://127.0.0.1:{port}/echo", "connection_id": made["id"]}
        flow = await create_flow(client, http_flow(call))
        run = await client.post(f"/flows/{flow['id']}/runs", json={"test": True, "input": {}})

    assert run.status_code == 200 and run.json()["status"] == "succeeded", run.text
    assert received[0]["headers"]["authorization"] == f"Bearer {KEY}"
    assert KEY not in run.text


@pytest.mark.usefixtures("box")
async def test_a_run_whose_connection_was_deleted_is_refused_before_it_starts(
    client: httpx.AsyncClient,
) -> None:
    made = (await client.post("/connections", json=bearer_body(hosts="127.0.0.1"))).json()
    call = {"url": "http://127.0.0.1:9/echo", "connection_id": made["id"]}
    flow = await create_flow(client, http_flow(call))
    await client.delete(f"/connections/{made['id']}?force=true")
    run = await client.post(f"/flows/{flow['id']}/runs", json={"test": True, "input": {}})
    assert run.status_code == 422 and run.json()["code"] == "connection_not_found"


@pytest.mark.usefixtures("box")
async def test_a_flow_that_calls_another_loads_the_connection_the_other_uses(
    client: httpx.AsyncClient,
) -> None:
    made = (await client.post("/connections", json=bearer_body(hosts="127.0.0.1"))).json()
    async with serve() as (port, received):
        call = {"url": f"http://127.0.0.1:{port}/echo", "connection_id": made["id"]}
        outputs = [{"name": "total", "type": "number", "value": "{{ nodes.call.output.status }}"}]
        child = await create_flow(client, http_flow(call, outputs))
        await publish(client, child["id"])
        parent = await create_flow(client, parent_draft(child["id"]))
        await publish(client, parent["id"])
        run = await client.post(f"/flows/{parent['id']}/runs", json={"input": {"amount": 1}})

    assert run.json()["status"] == "succeeded", run.text
    assert received[0]["headers"]["authorization"] == f"Bearer {KEY}"
    assert KEY not in run.text


async def make_service(client: httpx.AsyncClient) -> dict[str, Any]:
    body = {"type": "acme", "name": "Acme", "values": {"api_key": KEY}}
    return (await client.post("/connections", json=body)).json()


@pytest.mark.usefixtures("box")
async def test_the_test_call_sends_the_credentials_and_reports_acceptance(
    client: httpx.AsyncClient, with_service
) -> None:
    with_service()
    made = await make_service(client)
    async with serve() as (port, received):
        with_service(test_url=f"http://127.0.0.1:{port}/users/1")
        result = await client.post(f"/connections/{made['id']}/test")

    assert result.status_code == 200
    assert result.json() == {
        "ok": True,
        "status": 200,
        "message": "The service accepted the credentials.",
    }
    assert received[0]["headers"]["authorization"] == f"Bearer {KEY}"
    assert KEY not in result.text


@pytest.mark.usefixtures("box")
async def test_a_service_that_refuses_is_reported_not_raised(
    client: httpx.AsyncClient, with_service
) -> None:
    with_service()
    made = await make_service(client)
    async with serve() as (port, _):
        with_service(test_url=f"http://127.0.0.1:{port}/users/99")
        body = (await client.post(f"/connections/{made['id']}/test")).json()
    assert body["ok"] is False and body["status"] == 404


@pytest.mark.usefixtures("box")
async def test_an_unreachable_service_is_reported_without_a_status(
    client: httpx.AsyncClient, with_service
) -> None:
    with_service()
    made = await make_service(client)
    with_service(test_url="http://127.0.0.1:1/never")
    body = (await client.post(f"/connections/{made['id']}/test")).json()
    assert body["ok"] is False and body["status"] is None
    assert body["message"].startswith("Could not reach the service")


@pytest.mark.usefixtures("box")
async def test_a_type_without_a_test_is_refused_and_unknown_ids_are_404(
    client: httpx.AsyncClient,
) -> None:
    made = (await client.post("/connections", json=bearer_body())).json()
    refused = await client.post(f"/connections/{made['id']}/test")
    assert refused.status_code == 422 and refused.json()["code"] == "no_test_available"
    assert (await client.post(f"/connections/{uuid.uuid4()}/test")).status_code == 404
    other = await client.post(f"/connections/{made['id']}/test", headers=OTHER)
    assert other.status_code == 404


@pytest.mark.usefixtures("box")
async def test_the_openai_card_fills_in_the_default_base_url(client: httpx.AsyncClient) -> None:
    body = {"type": "openai_compatible", "name": "OpenAI-compatible", "values": {"api_key": KEY}}
    created = await client.post("/connections", json=body)
    assert created.status_code == 201
    assert created.json()["config"] == {"base_url": "https://api.openai.com/v1"}


@pytest.mark.usefixtures("box")
async def test_a_custom_base_url_is_kept_and_a_bad_one_is_refused(
    client: httpx.AsyncClient,
) -> None:
    values = {"api_key": KEY, "base_url": "https://api.groq.com/openai/v1"}
    ok = await client.post(
        "/connections", json={"type": "openai_compatible", "name": "Groq", "values": values}
    )
    assert ok.status_code == 201 and ok.json()["config"]["base_url"] == values["base_url"]
    for bad in ("api.groq.com", "ftp://x.com", "https://user:pw@x.com/v1"):
        response = await client.post(
            "/connections",
            json={
                "type": "openai_compatible",
                "name": f"x{bad}",
                "values": {**values, "base_url": bad},
            },
        )
        assert response.status_code == 422, bad
        assert response.json()["details"]["field"] == "base_url"


@pytest.mark.usefixtures("box")
async def test_the_openai_test_call_goes_to_the_base_url(client: httpx.AsyncClient) -> None:
    async with serve() as (port, received):
        base = f"http://127.0.0.1:{port}/users"
        values = {"api_key": KEY, "base_url": base}
        made = (
            await client.post(
                "/connections",
                json={"type": "openai_compatible", "name": "Local", "values": values},
            )
        ).json()
        result = await client.post(f"/connections/{made['id']}/test")

    assert result.json()["ok"] is True
    assert received[0]["target"] == "/users/models"
    assert received[0]["headers"]["authorization"] == f"Bearer {KEY}"


@pytest.mark.usefixtures("box")
async def test_a_connection_whose_type_is_gone_still_lists_and_can_be_deleted(
    client: httpx.AsyncClient, connection_store: FakeConnectionStore
) -> None:
    made = (await client.post("/connections", json=bearer_body())).json()
    next(iter(connection_store.rows.values())).type = "retired"

    listed = (await client.get("/connections")).json()["items"]
    assert [(c["type"], c["secrets_set"]) for c in listed] == [("retired", [])]
    refused = await client.patch(f"/connections/{made['id']}", json={"name": "x"})
    assert refused.status_code == 422 and refused.json()["code"] == "unknown_connection_type"
    assert (await client.delete(f"/connections/{made['id']}")).status_code == 204


@pytest.fixture
def small_cap() -> Iterator[None]:
    app.dependency_overrides[get_limits] = lambda: Limits(
        _env_file=None, max_connections_per_workspace=1
    )
    yield
    app.dependency_overrides.pop(get_limits, None)


@pytest.mark.usefixtures("box", "small_cap")
async def test_the_cap_blocks_a_new_connection_but_not_an_edit(client: httpx.AsyncClient) -> None:
    first = (await client.post("/connections", json=bearer_body("One"))).json()

    edited = await client.patch(f"/connections/{first['id']}", json={"name": "Renamed"})
    assert edited.status_code == 200
    blocked = await client.post("/connections", json=bearer_body("Two"))
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "connection_limit_reached"
    assert blocked.json()["details"]["limit"] == 1

    await client.delete(f"/connections/{first['id']}")
    assert (await client.post("/connections", json=bearer_body("Two"))).status_code == 201


@pytest.mark.usefixtures("box", "small_cap")
async def test_the_cap_is_per_workspace(client: httpx.AsyncClient) -> None:
    await client.post("/connections", json=bearer_body("One"))
    other = await client.post("/connections", json=bearer_body("One"), headers=OTHER)
    assert other.status_code == 201
