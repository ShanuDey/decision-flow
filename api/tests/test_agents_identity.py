# ruff: noqa: F811
import httpx
import pytest

from tests.agent_fakes import FakeAgentStore
from tests.test_agents_router import OTHER, agents, make_agent, tracer  # noqa: F401
from tests.test_node_http_request import anyio_backend  # noqa: F401

pytestmark = pytest.mark.anyio

API = {"x-df-source": "api"}


def as_user(external_user_id: str) -> dict[str, str]:
    return {**API, "x-external-user-id": external_user_id}


async def start(
    client: httpx.AsyncClient, agent: dict, headers: dict[str, str] | None = None
) -> dict:
    response = await client.post(f"/agents/{agent['id']}/threads", headers=headers)
    assert response.status_code == 201
    return response.json()


async def test_a_conversation_from_the_web_belongs_to_a_team_member(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    agent = await make_agent(client)
    made = await start(client, agent)

    assert (made["source"], made["external_user_id"], made["anonymous"]) == ("web", None, False)


async def test_the_web_ignores_an_external_user_id(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    agent = await make_agent(client)
    made = await start(client, agent, {"x-external-user-id": "maria"})

    assert (made["source"], made["external_user_id"]) == ("web", None)


async def test_an_api_key_names_the_person_in_a_header(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    agent = await make_agent(client)
    made = await start(client, agent, as_user(" maria "))

    assert (made["source"], made["external_user_id"], made["anonymous"]) == ("api", "maria", False)


async def test_a_missing_id_becomes_a_different_anonymous_id_each_time(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    agent = await make_agent(client)
    first = await start(client, agent, API)
    second = await start(client, agent, API)

    assert first["source"] == "api" and first["anonymous"] and second["anonymous"]
    assert first["external_user_id"].startswith("anon-")
    assert first["external_user_id"] != second["external_user_id"]


async def test_the_anonymous_id_sent_back_keeps_one_person_together(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    agent = await make_agent(client)
    first = await start(client, agent, API)
    again = await start(client, agent, as_user(first["external_user_id"]))
    path = f"/agents/{agent['id']}/threads"
    listed = await client.get(path, headers=as_user(first["external_user_id"]))

    assert again["external_user_id"] == first["external_user_id"]
    assert {t["id"] for t in listed.json()["items"]} == {first["id"], again["id"]}


@pytest.mark.parametrize("bad", [" ", "x" * 257])
async def test_an_invalid_external_user_id_is_refused(
    client: httpx.AsyncClient, agents: FakeAgentStore, bad: str
) -> None:
    agent = await make_agent(client)
    refused = await client.post(f"/agents/{agent['id']}/threads", headers=as_user(bad))

    assert (refused.status_code, refused.json()["code"]) == (422, "invalid_external_user_id")


async def test_an_api_key_must_name_the_person_to_list_conversations(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    agent = await make_agent(client)
    await start(client, agent, as_user("maria"))
    await start(client, agent, as_user("sam"))
    await start(client, agent)
    path = f"/agents/{agent['id']}/threads"

    bare = await client.get(path, headers=API)
    maria = await client.get(path, headers=as_user("maria"))
    everyone = await client.get(path)

    assert (bare.status_code, bare.json()["code"]) == (422, "external_user_id_required")
    assert [t["external_user_id"] for t in maria.json()["items"]] == ["maria"]
    assert len(everyone.json()["items"]) == 3


async def test_a_person_cannot_reach_another_persons_conversation(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    agent = await make_agent(client)
    maria = await start(client, agent, as_user("maria"))
    path = f"/agents/{agent['id']}/threads/{maria['id']}"

    assert (await client.get(path, headers=as_user("dev"))).status_code == 404
    assert (await client.delete(path, headers=as_user("dev"))).status_code == 404
    refused = await client.post(f"{path}/messages", json={"content": "Hi"}, headers=as_user("dev"))
    assert refused.status_code == 404
    assert (await client.get(path, headers=as_user("maria"))).status_code == 200
    assert (await client.get(path, headers=API)).status_code == 200
    assert (await client.delete(path, headers=as_user("maria"))).status_code == 204


async def test_an_app_that_names_its_user_cannot_open_a_team_conversation(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    agent = await make_agent(client)
    team = await start(client, agent)
    path = f"/agents/{agent['id']}/threads/{team['id']}"

    assert (await client.get(path, headers=as_user("maria"))).status_code == 404
    assert (await client.get(path)).status_code == 200


async def test_the_same_id_in_another_workspace_is_a_different_person(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    agent = await make_agent(client)
    maria = await start(client, agent, as_user("maria"))
    path = f"/agents/{agent['id']}/threads"
    stranger = {**OTHER, **as_user("maria")}

    assert (await client.get(f"{path}/{maria['id']}", headers=stranger)).status_code == 404
    assert (await client.get(path, headers=stranger)).status_code == 404
