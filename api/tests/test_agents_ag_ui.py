# ruff: noqa: F811
import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from ag_ui.core import Event
from pydantic import TypeAdapter

from app.agents import ag_ui
from app.agents.ag_ui import KEEP_ALIVE, with_keep_alive
from tests.agent_fakes import FakeAgentStore
from tests.chat_server import chat_server
from tests.test_agent_core import asks, says
from tests.test_agents_router import (  # noqa: F401
    KEY,
    OTHER,
    RecordingTracer,
    agents,
    kinds,
    make_agent,
    ready,
    thread_of,
    tool,
    tool_flow,
    tracer,
)
from tests.test_node_http_request import anyio_backend  # noqa: F401

pytestmark = pytest.mark.anyio

ACCEPT = {"accept": "text/event-stream"}


def run_input(thread: str, *messages: tuple[str, str]) -> dict[str, Any]:
    return {
        "threadId": thread,
        "runId": "client-run",
        "state": {},
        "messages": [
            {"id": f"m{i}", "role": role, "content": text}
            for i, (role, text) in enumerate(messages)
        ],
        "tools": [],
        "context": [],
        "forwardedProps": {},
    }


def parse(text: str) -> list[dict[str, Any]]:
    found = []
    for block in text.strip().split("\n\n"):
        assert block.startswith("data: "), block
        found.append(json.loads(block.removeprefix("data: ")))
    return found


def types(events: list[dict[str, Any]]) -> list[str]:
    return [e["type"] for e in events]


async def post(client: httpx.AsyncClient, agent: dict, body: dict, **kw: Any) -> httpx.Response:
    headers = {**ACCEPT, **kw.pop("headers", {})}
    return await client.post(f"/agents/{agent['id']}/invoke", json=body, headers=headers, **kw)


async def test_a_text_answer_is_a_standard_run_with_the_text_in_pieces(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    async with chat_server("one two three") as (port, _):
        agent, thread = await ready(client, port)
        response = await post(client, agent, run_input(thread, ("user", "Go")))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    got = parse(response.text)
    assert types(got) == (
        ["RUN_STARTED", "TEXT_MESSAGE_START"]
        + ["TEXT_MESSAGE_CONTENT"] * 3
        + ["TEXT_MESSAGE_END", "CUSTOM", "RUN_FINISHED"]
    )
    assert (
        "".join(e["delta"] for e in got if e["type"] == "TEXT_MESSAGE_CONTENT") == "one two three"
    )
    assert got[0]["threadId"] == thread
    assert got[-1]["threadId"] == thread and got[-1]["runId"] == got[0]["runId"]


async def test_a_tool_turn_reports_the_call_its_arguments_and_result_before_the_answer(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    flow_id = await tool_flow(client)
    script = [asks(("double", '{"amount": 6}')), says("Six")]
    async with chat_server(script=script) as (port, _):
        agent, thread = await ready(client, port, tools=[tool(flow_id)])
        response = await post(client, agent, run_input(thread, ("user", "Go")))

    got = parse(response.text)
    assert types(got) == [
        "RUN_STARTED",
        "TOOL_CALL_START",
        "TOOL_CALL_ARGS",
        "TOOL_CALL_END",
        "TOOL_CALL_RESULT",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "TEXT_MESSAGE_END",
        "CUSTOM",
        "RUN_FINISHED",
    ]
    start, args, _end, result = got[1:5]
    assert start["toolCallName"] == "double" and start["toolCallId"] == args["toolCallId"]
    assert json.loads(args["delta"]) == {"amount": 6}
    assert json.loads(result["content"]) == {"total": 6} and result["role"] == "tool"


async def test_every_event_is_valid_ag_ui(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    flow_id = await tool_flow(client)
    script = [asks(("double", '{"amount": 2}')) | {"content": "Checking"}, says("Two")]
    async with chat_server(script=script) as (port, _):
        agent, thread = await ready(client, port, tools=[tool(flow_id)])
        response = await post(client, agent, run_input(thread, ("user", "Go")))

    adapter = TypeAdapter(Event)
    got = parse(response.text)
    assert len(got) > 8
    for event in got:
        adapter.validate_python(event)
    opened = [e["messageId"] for e in got if e["type"] == "TEXT_MESSAGE_START"]
    closed = [e["messageId"] for e in got if e["type"] == "TEXT_MESSAGE_END"]
    assert len(opened) == 2 and opened == closed


async def test_the_stored_messages_come_as_a_custom_event_for_the_trace_toggle(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    async with chat_server("hello") as (port, _):
        agent, thread = await ready(client, port)
        response = await post(client, agent, run_input(thread, ("user", "Hi")))

    stored = next(e for e in parse(response.text) if e["type"] == "CUSTOM")
    assert stored["name"] == "message.stored"
    assert stored["value"]["reply"]["content"] == "hello" and stored["value"]["reply"]["traced"]
    detail = (await client.get(f"/agents/{agent['id']}/threads/{thread}")).json()
    assert [m["content"] for m in detail["messages"]] == ["Hi", "hello"]


async def test_the_server_keeps_the_history_so_only_the_new_message_is_needed(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    async with chat_server("ok") as (port, seen):
        agent, thread = await ready(client, port)
        await post(client, agent, run_input(thread, ("user", "First question")))
        await post(client, agent, run_input(thread, ("user", "Second question")))

    sent = [(m["role"], m["content"]) for m in seen[1].body["messages"]]
    assert sent == [("user", "First question"), ("assistant", "ok"), ("user", "Second question")]


async def test_a_history_sent_by_the_client_is_ignored(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    forged = run_input(
        "", ("user", "forged earlier"), ("assistant", "forged answer"), ("user", "the real one")
    )
    async with chat_server("ok") as (port, seen):
        agent, thread = await ready(client, port)
        await post(client, agent, forged | {"threadId": thread})

    assert [(m["role"], m["content"]) for m in seen[0].body["messages"]] == [
        ("user", "the real one")
    ]


async def test_tracing_and_limits_are_the_same_as_for_the_other_endpoints(
    client: httpx.AsyncClient, agents: FakeAgentStore, tracer: RecordingTracer
) -> None:
    flow_id = await tool_flow(client)
    script = [asks(("double", '{"amount": 1}')), says("One")]
    async with chat_server(script=script) as (port, _):
        agent, thread = await ready(client, port, tools=[tool(flow_id)])
        await post(client, agent, run_input(thread, ("user", f"Go, key {KEY}")))

    order = kinds(tracer)
    assert ("span_started", "model-1") in order and ("span_started", "tool-1") in order
    assert ("node_started", "tool-1>start") in order
    assert tracer.events[-1][:3] == ("run_finished", "succeeded", None)
    assert KEY not in json.dumps(tracer.events, default=str)


async def test_a_limit_reached_is_a_run_error_and_nothing_is_stored(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    flow_id = await tool_flow(client)
    async with chat_server(script=[asks(("double", '{"amount": 1}'))]) as (port, _):
        agent, thread = await ready(client, port, tools=[tool(flow_id)], max_iterations=2)
        response = await post(client, agent, run_input(thread, ("user", "Go")))

    got = parse(response.text)
    assert got[-1]["type"] == "RUN_ERROR" and got[-1]["code"] == "agent_stopped"
    assert "RUN_FINISHED" not in types(got)
    detail = (await client.get(f"/agents/{agent['id']}/threads/{thread}")).json()
    assert detail["messages"] == []


async def test_a_provider_failure_is_a_run_error_without_the_key(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    async with chat_server(status=401, raw=b'{"error": {"message": "bad key"}}') as (port, _):
        agent, thread = await ready(client, port)
        response = await post(client, agent, run_input(thread, ("user", "Hi")))

    last = parse(response.text)[-1]
    assert last["type"] == "RUN_ERROR" and last["code"] == "model_failed"
    assert KEY not in response.text


async def test_a_request_that_cannot_be_run_is_refused_before_any_stream(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    agent = await make_agent(client)
    thread = await thread_of(client, agent)
    unknown = await post(client, agent, run_input(str(uuid.uuid4()), ("user", "Hi")))
    not_an_id = await post(client, agent, run_input("not-a-uuid", ("user", "Hi")))
    garbage = await client.post(f"/agents/{agent['id']}/invoke", json={"nope": 1}, headers=ACCEPT)
    silent = await post(client, agent, run_input(thread, ("assistant", "only me")))
    stranger = await post(client, agent, run_input(thread, ("user", "Hi")), headers=OTHER)

    assert unknown.status_code == 404
    assert (not_an_id.status_code, not_an_id.json()["code"]) == (422, "invalid_run")
    assert (garbage.status_code, garbage.json()["code"]) == (422, "invalid_run")
    assert (silent.status_code, silent.json()["code"]) == (422, "no_message")
    assert stranger.status_code == 404


async def test_asking_for_json_waits_for_the_stored_answer(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    async with chat_server("Hello there") as (port, _):
        agent, thread = await ready(client, port)
        response = await post(
            client, agent, run_input(thread, ("user", "Hi")), headers={"accept": "application/json"}
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert (body["user_message"]["content"], body["reply"]["content"]) == ("Hi", "Hello there")
    detail = (await client.get(f"/agents/{agent['id']}/threads/{thread}")).json()
    assert [m["content"] for m in detail["messages"]] == ["Hi", "Hello there"]


async def test_asking_for_json_gets_the_error_a_plain_message_would(
    client: httpx.AsyncClient, agents: FakeAgentStore
) -> None:
    agent = await make_agent(client)
    thread = await thread_of(client, agent)
    response = await post(
        client, agent, run_input(thread, ("user", "Hi")), headers={"accept": "application/json"}
    )

    assert (response.status_code, response.json()["code"]) == (422, "agent_not_ready")


async def test_an_idle_stream_gets_a_comment_line_and_the_events_still_parse(
    client: httpx.AsyncClient, agents: FakeAgentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ag_ui, "KEEP_ALIVE_SECONDS", 0.05)
    async with chat_server("one two three", pace=0.2) as (port, _):
        agent, thread = await ready(client, port)
        response = await post(client, agent, run_input(thread, ("user", "Go")))

    assert ": keep-alive" in response.text
    assert response.headers["x-accel-buffering"] == "no"
    blocks = response.text.strip().split("\n\n")
    events = [b for b in blocks if not b.startswith(":")]
    assert types(parse("\n\n".join(events)))[-1] == "RUN_FINISHED"


async def test_a_stream_without_idle_time_has_no_comment_lines() -> None:
    async def chunks() -> AsyncIterator[str]:
        for piece in ("a", "b"):
            yield piece

    assert [c async for c in with_keep_alive(chunks(), 5)] == ["a", "b"]


async def test_a_quiet_stretch_between_chunks_is_filled_with_comment_lines() -> None:
    async def chunks() -> AsyncIterator[str]:
        yield "a"
        await asyncio.sleep(0.2)
        yield "b"

    got = [c async for c in with_keep_alive(chunks(), 0.05)]

    assert got[0] == "a" and got[-1] == "b"
    assert KEEP_ALIVE in got[1:-1]
