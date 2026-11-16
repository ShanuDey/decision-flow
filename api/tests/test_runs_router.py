import copy
import uuid

import httpx
import pytest
from cryptography.fernet import Fernet

from app.main import app
from app.secrets.crypto import SecretBox, get_box_factory
from app.settings import Settings, get_settings
from tests.conftest import FakeRunStore, create_flow, example


@pytest.mark.anyio
async def test_test_run_returns_the_output(
    client: httpx.AsyncClient, run_store: FakeRunStore
) -> None:
    flow = await create_flow(client, example("assign-variable.json"))
    response = await client.post(
        f"/flows/{flow['id']}/runs?wait=true", json={"test": True, "input": {"amount": 5}}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["output"] == {"total": 5, "label": "Order total 5"}
    detail = (await client.get(f"/runs/{body['run_id']}")).json()
    assert detail["run_id"] == body["run_id"]
    assert (detail["status"], detail["output"], detail["input"]) == (
        "succeeded",
        body["output"],
        {"amount": 5},
    )
    assert detail["flow_id"] == flow["id"]
    assert detail["test"] is True and detail["started_at"]
    assert "mlflow_trace_id" not in body
    assert next(iter(run_store.runs.values())).mlflow_trace_id == "tr-stub"


@pytest.mark.anyio
async def test_bad_input_is_422_naming_the_field_and_creates_no_run(
    client: httpx.AsyncClient, run_store: FakeRunStore
) -> None:
    flow = await create_flow(client, example("assign-variable.json"))
    response = await client.post(
        f"/flows/{flow['id']}/runs", json={"test": True, "input": {"amount": "5"}}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"
    assert response.json()["details"]["field"] == "amount"
    assert run_store.runs == {}


@pytest.mark.anyio
async def test_running_an_invalid_flow_is_422(
    client: httpx.AsyncClient, run_store: FakeRunStore
) -> None:
    broken = copy.deepcopy(example("start-end.json"))
    broken["edges"] = []
    flow = await create_flow(client, broken)
    response = await client.post(f"/flows/{flow['id']}/runs", json={"test": True})
    assert response.status_code == 422 and response.json()["code"] == "invalid_flow"
    assert run_store.runs == {}


async def replace_draft(client: httpx.AsyncClient, flow_id: str, draft: dict) -> None:
    version = (await client.get(f"/flows/{flow_id}")).json()["draft_version"]
    saved = await client.put(
        f"/flows/{flow_id}/draft", json=draft, headers={"If-Match": str(version)}
    )
    assert saved.status_code == 200


@pytest.mark.anyio
async def test_a_non_test_run_of_an_unpublished_flow_is_refused(
    client: httpx.AsyncClient, run_store: FakeRunStore
) -> None:
    flow = await create_flow(client)
    response = await client.post(f"/flows/{flow['id']}/runs", json={"input": {}})
    assert response.status_code == 422 and response.json()["code"] == "not_published"
    assert "publish" in response.json()["message"]
    assert run_store.runs == {}


@pytest.mark.anyio
async def test_a_published_run_uses_the_published_version_not_the_draft(
    client: httpx.AsyncClient, run_store: FakeRunStore
) -> None:
    flow = await create_flow(client, example("assign-variable.json"))
    assert (await client.post(f"/flows/{flow['id']}/publish")).status_code == 201
    await replace_draft(client, flow["id"], example("start-end.json"))

    response = await client.post(f"/flows/{flow['id']}/runs", json={"input": {"amount": 5}})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["output"] == {"total": 5, "label": "Order total 5"}
    assert body["flow_version"] == 1
    saved = run_store.runs[uuid.UUID(body["run_id"])]
    assert saved.test is False and saved.flow_version == 1


@pytest.mark.anyio
async def test_publishing_again_changes_which_version_runs(
    client: httpx.AsyncClient, run_store: FakeRunStore
) -> None:
    flow = await create_flow(client, example("assign-variable.json"))
    assert (await client.post(f"/flows/{flow['id']}/publish")).status_code == 201
    await replace_draft(client, flow["id"], example("start-end.json"))
    assert (await client.post(f"/flows/{flow['id']}/publish")).status_code == 201

    response = await client.post(f"/flows/{flow['id']}/runs", json={"input": {"amount": 5}})

    assert response.status_code == 200
    assert response.json()["flow_version"] == 2
    assert response.json()["output"] == {"amount": 5, "tier": "silver"}


@pytest.mark.anyio
async def test_a_published_run_shows_its_version_in_the_run_and_the_list(
    client: httpx.AsyncClient,
) -> None:
    flow = await create_flow(client, example("assign-variable.json"))
    assert (await client.post(f"/flows/{flow['id']}/publish")).status_code == 201
    published = (
        await client.post(f"/flows/{flow['id']}/runs", json={"input": {"amount": 1}})
    ).json()
    tested = (
        await client.post(f"/flows/{flow['id']}/runs", json={"test": True, "input": {"amount": 1}})
    ).json()
    assert tested["flow_version"] is None

    detail = (await client.get(f"/runs/{published['run_id']}")).json()
    assert (detail["test"], detail["flow_version"]) == (False, 1)

    real = (await client.get("/runs", params={"test": "false"})).json()["items"]
    assert [r["run_id"] for r in real] == [published["run_id"]]
    assert real[0]["flow_version"] == 1


@pytest.mark.anyio
async def test_running_a_missing_flow_is_404(client: httpx.AsyncClient) -> None:
    response = await client.post(f"/flows/{uuid.uuid4()}/runs", json={"test": True})
    assert response.status_code == 404


@pytest.mark.anyio
async def test_unknown_run_is_404(client: httpx.AsyncClient) -> None:
    assert (await client.get(f"/runs/{uuid.uuid4()}")).status_code == 404


@pytest.mark.anyio
async def test_malformed_ids_use_the_shared_error_shape(client: httpx.AsyncClient) -> None:
    response = await client.get("/runs/not-a-uuid")
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_request"
    assert body["details"]["field"] == "run_id"
    assert body["details"]["errors"][0]["field"] == "run_id"


async def _run(client: httpx.AsyncClient, flow_id: str, amount: object) -> None:
    await client.post(f"/flows/{flow_id}/runs", json={"test": True, "input": {"amount": amount}})


@pytest.mark.anyio
async def test_list_runs_pages_newest_first_with_a_cursor(client: httpx.AsyncClient) -> None:
    flow = await create_flow(client, example("assign-variable.json"))
    for amount in (1, 2, 3):
        await _run(client, flow["id"], amount)

    first = (await client.get("/runs", params={"limit": 2})).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    assert first["items"][0]["started_at"] >= first["items"][1]["started_at"]

    params = {"limit": 2, "cursor": first["next_cursor"]}
    second = (await client.get("/runs", params=params)).json()
    assert len(second["items"]) == 1 and second["next_cursor"] is None
    seen = [i["run_id"] for i in first["items"] + second["items"]]
    assert len(set(seen)) == 3
    assert "output" not in first["items"][0]


@pytest.mark.anyio
async def test_list_runs_filters(client: httpx.AsyncClient) -> None:
    one = await create_flow(client, example("assign-variable.json"))
    two = await create_flow(client, example("assign-variable.json"))
    await _run(client, one["id"], 1)
    await _run(client, two["id"], 2)

    only_one = (await client.get("/runs", params={"flow_id": one["id"]})).json()
    assert [i["flow_id"] for i in only_one["items"]] == [one["id"]]
    assert (await client.get("/runs", params={"status": "failed"})).json()["items"] == []
    assert (await client.get("/runs", params={"test": False})).json()["items"] == []
    future = (await client.get("/runs", params={"from": "2999-01-01T00:00:00"})).json()
    assert future["items"] == []


@pytest.mark.anyio
async def test_list_runs_rejects_a_bad_cursor_and_limit(client: httpx.AsyncClient) -> None:
    bad = await client.get("/runs", params={"cursor": "garbage"})
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_cursor"
    too_big = await client.get("/runs", params={"limit": 101})
    assert too_big.status_code == 422 and too_big.json()["code"] == "invalid_request"


def new_box() -> SecretBox:
    return SecretBox([Fernet.generate_key().decode()])


async def run_naming_secrets(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, *names: str
) -> httpx.Response:
    monkeypatch.setattr("app.runs.service.referenced_secret_names", lambda _graph: set(names))
    flow = await create_flow(client, example("assign-variable.json"))
    return await client.post(
        f"/flows/{flow['id']}/runs?wait=true", json={"test": True, "input": {"amount": 5}}
    )


@pytest.mark.anyio
async def test_a_run_fails_before_starting_when_a_secret_is_missing(
    client: httpx.AsyncClient, run_store: FakeRunStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = await run_naming_secrets(client, monkeypatch, "API_KEY", "OTHER_KEY")

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "secret_not_found"
    assert body["details"]["names"] == ["API_KEY", "OTHER_KEY"]
    assert run_store.runs == {}


@pytest.mark.anyio
async def test_a_run_with_all_its_secrets_goes_ahead(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    box = new_box()
    app.dependency_overrides[get_box_factory] = lambda: lambda: box
    try:
        await client.put("/secrets/API_KEY", json={"value": "sk_live_1234567890"})
        response = await run_naming_secrets(client, monkeypatch, "API_KEY")
    finally:
        app.dependency_overrides.pop(get_box_factory, None)

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"


@pytest.mark.anyio
async def test_a_secret_saved_under_another_key_is_reported_not_crashed(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    old, new = new_box(), new_box()
    try:
        app.dependency_overrides[get_box_factory] = lambda: lambda: old
        await client.put("/secrets/API_KEY", json={"value": "sk_live_1234567890"})
        app.dependency_overrides[get_box_factory] = lambda: lambda: new
        response = await run_naming_secrets(client, monkeypatch, "API_KEY")
    finally:
        app.dependency_overrides.pop(get_box_factory, None)

    assert response.status_code == 500
    assert response.json()["code"] == "secret_unreadable"
    assert "sk_live_1234567890" not in response.text


@pytest.mark.anyio
async def test_a_run_that_uses_no_secret_needs_no_encryption_key(
    client: httpx.AsyncClient,
) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, encryption_key="")
    try:
        flow = await create_flow(client, example("assign-variable.json"))
        response = await client.post(
            f"/flows/{flow['id']}/runs?wait=true", json={"test": True, "input": {"amount": 5}}
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
