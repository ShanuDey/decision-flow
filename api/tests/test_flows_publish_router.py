import uuid

import httpx
import pytest

from tests.auth_helpers import bearer
from tests.conftest import FakeFlowStore, create_flow

pytestmark = pytest.mark.anyio

OTHER = bearer(sub="user-2")


async def edit(client: httpx.AsyncClient, flow: dict, name: str) -> dict:
    draft = {**flow["draft"], "nodes": [dict(n) for n in flow["draft"]["nodes"]]}
    draft["nodes"][0]["name"] = name
    version = (await client.get(f"/flows/{flow['id']}")).json()["draft_version"]
    saved = await client.put(
        f"/flows/{flow['id']}/draft", json=draft, headers={"If-Match": str(version)}
    )
    assert saved.status_code == 200
    return draft


async def test_publish_creates_version_one_and_marks_the_flow(client: httpx.AsyncClient) -> None:
    flow = await create_flow(client)
    response = await client.post(f"/flows/{flow['id']}/publish")
    assert response.status_code == 201
    body = response.json()
    assert (body["version"], body["source_draft_version"]) == (1, 1)
    assert body["graph"] == flow["draft"]

    detail = (await client.get(f"/flows/{flow['id']}")).json()
    assert (detail["published_version"], detail["published_draft_version"]) == (1, 1)
    assert detail["published_at"] is not None
    assert (await client.get(f"/flows/{flow['id']}")).json()["draft"] == flow["draft"]


async def test_a_flow_that_was_never_published_has_no_published_fields(
    client: httpx.AsyncClient,
) -> None:
    flow = await create_flow(client)
    assert flow["published_version"] is None and flow["published_at"] is None


async def test_publishing_after_an_edit_creates_the_next_version(
    client: httpx.AsyncClient,
) -> None:
    flow = await create_flow(client)
    await client.post(f"/flows/{flow['id']}/publish")
    await edit(client, flow, "Begin")
    second = await client.post(f"/flows/{flow['id']}/publish")
    assert second.status_code == 201
    assert (second.json()["version"], second.json()["source_draft_version"]) == (2, 2)
    listed = (await client.get(f"/flows/{flow['id']}/versions")).json()["items"]
    assert [v["version"] for v in listed] == [2, 1]


async def test_a_published_version_does_not_change_when_the_draft_is_edited(
    client: httpx.AsyncClient,
) -> None:
    flow = await create_flow(client)
    await client.post(f"/flows/{flow['id']}/publish")
    await edit(client, flow, "Begin")
    first = (await client.get(f"/flows/{flow['id']}/versions/1")).json()
    assert first["graph"] == flow["draft"]


async def test_publishing_an_unchanged_draft_is_a_conflict(client: httpx.AsyncClient) -> None:
    flow = await create_flow(client)
    await client.post(f"/flows/{flow['id']}/publish")
    again = await client.post(f"/flows/{flow['id']}/publish")
    assert again.status_code == 409 and again.json()["code"] == "nothing_to_publish"
    assert len((await client.get(f"/flows/{flow['id']}/versions")).json()["items"]) == 1


async def test_publishing_an_invalid_draft_names_the_problem(client: httpx.AsyncClient) -> None:
    flow = await create_flow(client)
    await client.put(f"/flows/{flow['id']}/draft", json={}, headers={"If-Match": "1"})
    response = await client.post(f"/flows/{flow['id']}/publish")
    assert response.status_code == 422 and response.json()["code"] == "invalid_flow"
    assert (await client.get(f"/flows/{flow['id']}/versions")).json()["items"] == []


async def test_a_draft_that_moves_on_during_publish_is_a_conflict(
    client: httpx.AsyncClient, flow_store: FakeFlowStore
) -> None:
    flow = await create_flow(client)
    real = flow_store.publish

    async def racing(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        await edit(client, flow, "Begin")
        return await real(*args, **kwargs)

    flow_store.publish = racing  # type: ignore[method-assign]
    response = await client.post(f"/flows/{flow['id']}/publish")
    assert response.status_code == 409 and response.json()["code"] == "draft_conflict"
    assert response.json()["details"]["draft_version"] == 2


async def test_unknown_flow_and_version_are_404(client: httpx.AsyncClient) -> None:
    missing = uuid.uuid4()
    assert (await client.post(f"/flows/{missing}/publish")).status_code == 404
    assert (await client.get(f"/flows/{missing}/versions")).status_code == 404
    flow = await create_flow(client)
    assert (await client.get(f"/flows/{flow['id']}/versions/1")).status_code == 404


async def test_another_workspace_cannot_publish_or_read_versions(
    client: httpx.AsyncClient,
) -> None:
    flow = await create_flow(client)
    await client.post(f"/flows/{flow['id']}/publish")
    url = f"/flows/{flow['id']}"
    assert (await client.post(f"{url}/publish", headers=OTHER)).status_code == 404
    assert (await client.get(f"{url}/versions", headers=OTHER)).status_code == 404
    assert (await client.get(f"{url}/versions/1", headers=OTHER)).status_code == 404
    assert (await client.get(f"{url}/versions")).status_code == 200


async def test_unpublish_clears_the_published_fields_and_keeps_the_versions(
    client: httpx.AsyncClient,
) -> None:
    flow = await create_flow(client)
    await client.post(f"/flows/{flow['id']}/publish")
    response = await client.post(f"/flows/{flow['id']}/unpublish")
    assert response.status_code == 200
    body = response.json()
    assert (body["published_version"], body["published_draft_version"], body["published_at"]) == (
        None,
        None,
        None,
    )
    versions = (await client.get(f"/flows/{flow['id']}/versions")).json()["items"]
    assert [v["version"] for v in versions] == [1]
    assert (await client.get(f"/flows/{flow['id']}")).json()["draft"] == flow["draft"]


async def test_publishing_again_after_unpublish_continues_the_numbering(
    client: httpx.AsyncClient,
) -> None:
    flow = await create_flow(client)
    await client.post(f"/flows/{flow['id']}/publish")
    await client.post(f"/flows/{flow['id']}/unpublish")
    again = await client.post(f"/flows/{flow['id']}/publish")
    assert again.status_code == 201 and again.json()["version"] == 2
    detail = (await client.get(f"/flows/{flow['id']}")).json()
    assert detail["published_version"] == 2


async def test_a_flow_that_is_not_published_cannot_be_unpublished(
    client: httpx.AsyncClient,
) -> None:
    flow = await create_flow(client)
    response = await client.post(f"/flows/{flow['id']}/unpublish")
    assert response.status_code == 409 and response.json()["code"] == "not_published"
    await client.post(f"/flows/{flow['id']}/publish")
    await client.post(f"/flows/{flow['id']}/unpublish")
    again = await client.post(f"/flows/{flow['id']}/unpublish")
    assert again.status_code == 409 and again.json()["code"] == "not_published"


async def test_a_run_of_an_unpublished_flow_is_refused(client: httpx.AsyncClient) -> None:
    flow = await create_flow(client)
    await client.post(f"/flows/{flow['id']}/publish")
    await client.post(f"/flows/{flow['id']}/unpublish")
    run = await client.post(f"/flows/{flow['id']}/runs", json={"input": {}})
    assert run.status_code == 422 and run.json()["code"] == "not_published"


async def test_unpublishing_an_unknown_flow_is_404(client: httpx.AsyncClient) -> None:
    assert (await client.post(f"/flows/{uuid.uuid4()}/unpublish")).status_code == 404


async def test_another_user_cannot_unpublish_the_flow(client: httpx.AsyncClient) -> None:
    flow = await create_flow(client)
    await client.post(f"/flows/{flow['id']}/publish")
    other = await client.post(f"/flows/{flow['id']}/unpublish", headers=OTHER)
    assert other.status_code == 404
    assert (await client.get(f"/flows/{flow['id']}")).json()["published_version"] == 1
