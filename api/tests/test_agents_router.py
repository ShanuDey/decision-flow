import json
import uuid
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from cryptography.fernet import Fernet

from app.agents.models import AgentMessage
from app.agents.service import HISTORY_CHARS, HISTORY_MESSAGES, _history
from app.agents.store import get_agent_store
from app.main import app
from app.secrets.crypto import SecretBox, get_box, get_box_factory
from tests.agent_fakes import FakeAgentStore
from tests.auth_helpers import bearer
from tests.chat_server import chat_server
from tests.conftest import FakeConnectionStore, create_flow
from tests.test_agent_core import asks, says
from tests.test_node_http_request import anyio_backend  # noqa: F401
from tests.test_node_subflow import child_draft, publish

pytestmark = pytest.mark.anyio

OTHER = bearer(sub="user-2")
KEY = "test-key-for-the-agent-router"


@pytest.fixture
def agents(connection_store: FakeConnectionStore) -> Iterator[FakeAgentStore]:
    store = FakeAgentStore()
    connection_store.agents = store
    app.dependency_overrides[get_agent_store] = lambda: store
    secret_box = SecretBox([Fernet.generate_key().decode()])
    app.dependency_overrides[get_box] = lambda: secret_box
    app.dependency_overrides[get_box_factory] = lambda: lambda: secret_box
    yield store
    for dep in (get_agent_store, get_box, get_box_factory):
        app.dependency_overrides.pop(dep, None)


async def connection(client: httpx.AsyncClient, port: int = 9, name: str = "Local model") -> str:
    body = {
        "type": "openai_compatible",
        "name": name,
        "values": {"base_url": f"http://127.0.0.1:{port}/v1", "api_key": KEY, "default_model": "m"},
    }
    response = await client.post("/connections", json=body)
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def tool_flow(client: httpx.AsyncClient) -> str:
    flow = await create_flow(client, child_draft())
    await publish(client, flow["id"])
    return flow["id"]


def tool(flow_id: str, name: str = "double") -> dict[str, str]:
    return {"flow_id": flow_id, "name": name, "description": "Returns the amount"}


async def make_agent(client: httpx.AsyncClient, **fields: Any) -> dict[str, Any]:
    response = await client.post("/agents", json={"name": "Helper"} | fields)
    assert response.status_code == 201, response.text
    return response.json()


async def thread_of(client: httpx.AsyncClient, agent: dict[str, Any]) -> str:
    response = await client.post(f"/agents/{agent['id']}/threads")
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def ready(client: httpx.AsyncClient, port: int, **fields: Any) -> tuple[dict, str]:
    agent = await make_agent(client, connection_id=await connection(client, port), **fields)
    return agent, await thread_of(client, agent)


async def test_an_agent_is_created_read_changed_and_deleted(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    conn = await connection(client)
    flow_id = await tool_flow(client)
    made = await make_agent(
        client, connection_id=conn, instructions="Be brief", tools=[tool(flow_id)], max_iterations=3
    )
    assert made["max_iterations"] == 3 and made["tools"][0]["name"] == "double"
    assert (await client.get(f"/agents/{made['id']}")).json() == made
    assert [a["name"] for a in (await client.get("/agents")).json()["items"]] == ["Helper"]

    changed = await client.patch(
        f"/agents/{made['id']}",
        json={"name": "Renamed", "max_total_tokens": 500, "max_iterations": None, "model": "x/y"},
    )
    body = changed.json()
    assert changed.status_code == 200, body
    assert (body["name"], body["max_total_tokens"], body["model"]) == ("Renamed", 500, "x/y")
    assert body["max_iterations"] == 3 and body["tools"] == made["tools"]
    cleared = await client.patch(f"/agents/{made['id']}", json={"max_total_tokens": None})
    assert cleared.json()["max_total_tokens"] is None

    assert (await client.delete(f"/agents/{made['id']}")).status_code == 204
    assert (await client.get(f"/agents/{made['id']}")).status_code == 404
    assert agents.agents == {}


async def test_what_cannot_work_is_refused_when_saving(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    flow_id = await tool_flow(client)
    await make_agent(client)
    cases = [
        ({"connection_id": str(uuid.uuid4())}, "connection_not_found"),
        ({"tools": [tool(flow_id, "bad name")]}, "invalid_tools"),
        ({"tools": [tool(flow_id), tool(flow_id)]}, "invalid_tools"),
        ({"tools": [{**tool(flow_id), "description": " "}]}, "invalid_tools"),
        ({"tools": [tool(str(uuid.uuid4()))]}, "tool_flow_not_found"),
        ({"name": "Helper"}, "agent_name_taken"),
    ]
    for fields, code in cases:
        response = await client.post("/agents", json={"name": "Other"} | fields)
        assert response.status_code in {409, 422}, (fields, response.text)
        assert response.json()["code"] == code, (fields, response.text)


async def test_agents_and_threads_are_private_to_the_workspace(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    agent = await make_agent(client)
    thread = await thread_of(client, agent)
    for path in (f"/agents/{agent['id']}", f"/agents/{agent['id']}/threads/{thread}"):
        assert (await client.get(path, headers=OTHER)).status_code == 404
    assert (await client.get("/agents", headers=OTHER)).json() == {"items": []}
    assert (await client.delete(f"/agents/{agent['id']}", headers=OTHER)).status_code == 404


async def test_a_message_is_answered_and_the_conversation_is_kept(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    async with chat_server("Hello there") as (port, seen):
        agent, thread = await ready(client, port, instructions="Be brief")
        first = await client.post(
            f"/agents/{agent['id']}/threads/{thread}/messages", json={"content": "Hi"}
        )
        second = await client.post(
            f"/agents/{agent['id']}/threads/{thread}/messages", json={"content": "And again?"}
        )

    assert first.status_code == 200, first.text
    body = first.json()
    assert body["user_message"]["content"] == "Hi" and body["user_message"]["seq"] == 1
    assert body["reply"]["content"] == "Hello there" and body["reply"]["seq"] == 2
    assert body["reply"]["usage"]["total_tokens"] == 5 and body["reply"]["steps"] == []
    sent = [(m["role"], m["content"]) for m in seen[1].body["messages"]]
    assert sent == [
        ("system", "Be brief"),
        ("user", "Hi"),
        ("assistant", "Hello there"),
        ("user", "And again?"),
    ]
    assert second.status_code == 200

    detail = (await client.get(f"/agents/{agent['id']}/threads/{thread}")).json()
    assert [m["seq"] for m in detail["messages"]] == [1, 2, 3, 4]
    assert detail["thread"]["title"] == "Hi"
    listed = (await client.get(f"/agents/{agent['id']}/threads")).json()["items"]
    assert [t["id"] for t in listed] == [thread]
    assert (await client.delete(f"/agents/{agent['id']}/threads/{thread}")).status_code == 204
    assert (await client.get(f"/agents/{agent['id']}/threads/{thread}")).status_code == 404


async def test_the_agent_runs_a_flow_and_the_message_shows_what_it_did(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    flow_id = await tool_flow(client)
    script = [asks(("double", '{"amount": 21}')), says("It is 21")]
    async with chat_server(script=script) as (port, seen):
        agent, thread = await ready(client, port, tools=[tool(flow_id)])
        response = await client.post(
            f"/agents/{agent['id']}/threads/{thread}/messages", json={"content": "Go"}
        )

    reply = response.json()["reply"]
    assert reply["content"] == "It is 21"
    (step,) = reply["steps"]
    assert (step["name"], step["arguments"], step["is_error"]) == ("double", {"amount": 21}, False)
    assert json.loads(step["result"]) == {"total": 21}
    assert seen[0].body["tools"][0]["function"]["name"] == "double"
    assert response.json()["user_message"]["steps"] is None


async def test_a_failed_turn_stores_nothing(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    async with chat_server(status=401, raw=b'{"error": {"message": "bad key"}}') as (port, _):
        agent, thread = await ready(client, port)
        response = await client.post(
            f"/agents/{agent['id']}/threads/{thread}/messages", json={"content": "Hi"}
        )

    assert response.status_code == 502 and response.json()["code"] == "model_failed"
    assert KEY not in response.text
    detail = (await client.get(f"/agents/{agent['id']}/threads/{thread}")).json()
    assert detail["messages"] == [] and detail["thread"]["title"] == ""


async def test_an_agent_without_a_connection_says_what_to_do(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    agent = await make_agent(client)
    thread = await thread_of(client, agent)
    response = await client.post(
        f"/agents/{agent['id']}/threads/{thread}/messages", json={"content": "Hi"}
    )
    assert response.status_code == 422 and response.json()["code"] == "agent_not_ready"


async def test_a_limit_reached_before_an_answer_is_reported(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    flow_id = await tool_flow(client)
    async with chat_server(script=[asks(("double", '{"amount": 1}'))]) as (port, _):
        agent, thread = await ready(client, port, tools=[tool(flow_id)], max_iterations=2)
        response = await client.post(
            f"/agents/{agent['id']}/threads/{thread}/messages", json={"content": "Go"}
        )

    assert response.status_code == 422 and response.json()["code"] == "agent_stopped"


async def test_a_flow_that_is_no_longer_published_stops_the_turn_clearly(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    flow_id = await tool_flow(client)
    async with chat_server("hi") as (port, seen):
        agent, thread = await ready(client, port, tools=[tool(flow_id)])
        await client.post(f"/flows/{flow_id}/unpublish")
        response = await client.post(
            f"/agents/{agent['id']}/threads/{thread}/messages", json={"content": "Go"}
        )

    assert response.status_code == 422 and response.json()["code"] == "agent_not_ready"
    assert seen == []


def events(text: str) -> list[tuple[str, Any]]:
    found = []
    for block in text.strip().split("\n\n"):
        name, data = block.split("\n")
        found.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return found


async def test_the_stream_reports_each_flow_then_the_answer(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    flow_id = await tool_flow(client)
    script = [asks(("double", '{"amount": 4}')), says("Four")]
    async with chat_server(script=script) as (port, _):
        agent, thread = await ready(client, port, tools=[tool(flow_id)])
        response = await client.post(
            f"/agents/{agent['id']}/threads/{thread}/messages/stream", json={"content": "Go"}
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    got = events(response.text)
    assert [name for name, _ in got] == ["tool", "message"]
    assert got[0][1]["name"] == "double" and got[0][1]["is_error"] is False
    assert got[1][1]["reply"]["content"] == "Four"
    detail = (await client.get(f"/agents/{agent['id']}/threads/{thread}")).json()
    assert len(detail["messages"]) == 2


async def test_a_failure_in_the_stream_is_an_error_event(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    agent = await make_agent(client)
    thread = await thread_of(client, agent)
    response = await client.post(
        f"/agents/{agent['id']}/threads/{thread}/messages/stream", json={"content": "Go"}
    )

    ((name, body),) = events(response.text)
    assert name == "error" and body["code"] == "agent_not_ready"


async def test_a_connection_that_an_agent_uses_cannot_be_deleted_quietly(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    conn = await connection(client)
    await make_agent(client, connection_id=conn)
    refused = await client.delete(f"/connections/{conn}")
    assert refused.status_code == 409
    assert refused.json()["details"]["agents"][0]["name"] == "Helper"


def message(seq: int, text: str) -> AgentMessage:
    return AgentMessage(seq=seq, role="user" if seq % 2 else "assistant", content=text)


def test_only_the_latest_messages_are_sent_back() -> None:
    many = [message(i, "x") for i in range(1, HISTORY_MESSAGES + 11)]
    sent = _history(many)
    assert len(sent) == HISTORY_MESSAGES
    assert sent[-1]["content"] == "x" and sent[0]["role"] == many[10].role


def test_a_long_thread_is_cut_by_size_but_keeps_the_newest_message() -> None:
    big = "y" * (HISTORY_CHARS // 2 + 1)
    sent = _history([message(1, big), message(2, big), message(3, big)])
    assert [m["content"] for m in sent] == [big]
    assert _history([]) == []
