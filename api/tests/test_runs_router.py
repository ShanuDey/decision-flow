import copy
import uuid

import httpx
import pytest

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
    assert (await client.get(f"/runs/{body['run_id']}")).json() == body
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


@pytest.mark.anyio
async def test_a_non_test_run_is_refused_until_publish_exists(client: httpx.AsyncClient) -> None:
    flow = await create_flow(client)
    response = await client.post(f"/flows/{flow['id']}/runs", json={"input": {}})
    assert response.status_code == 422 and response.json()["code"] == "not_published"


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
