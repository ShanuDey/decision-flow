import asyncio
import json
from typing import Any

import pytest

from app.connections.catalog import BY_ID
from app.connections.types import resolve
from app.engine.connections import ResolvedConnection
from app.engine.llm import AgentLimits, ToolSpec, run_agent
from tests.chat_server import chat_server
from tests.test_node_http_request import anyio_backend, policy  # noqa: F401

pytestmark = pytest.mark.anyio

CONNECTION_ID = "5f0a2c1e-7b3d-4e6a-9c8f-1d2e3f4a5b6c"
TOKEN = "test-token-for-the-agent"
ADD = ToolSpec(
    name="add",
    description="Add two numbers",
    parameters={"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}},
)


def connection(port: int) -> ResolvedConnection:
    values = {"api_key": TOKEN, "base_url": f"http://127.0.0.1:{port}/v1", "default_model": "m"}
    return resolve(BY_ID["openai_compatible"], CONNECTION_ID, "Local model", values)


def asks(*calls: tuple[str, str], tokens: int = 5) -> dict[str, Any]:
    """A model turn that calls tools: (name, raw JSON arguments) for each."""
    return {
        "role": "assistant",
        "content": None,
        "finish_reason": "tool_calls",
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": tokens},
        "tool_calls": [
            {"id": f"call_{i}", "type": "function", "function": {"name": n, "arguments": a}}
            for i, (n, a) in enumerate(calls)
        ],
    }


def says(text: str, tokens: int = 5) -> dict[str, Any]:
    usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": tokens}
    return {"role": "assistant", "content": text, "usage": usage}


class Tools:
    def __init__(self, result: str = "3", error: Exception | None = None, wait: float = 0) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.result, self.error, self.wait = result, error, wait

    async def __call__(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, arguments))
        await asyncio.sleep(self.wait)
        if self.error:
            raise self.error
        return self.result


async def agent(port: int, runner: Tools, **overrides: Any):
    options: dict[str, Any] = {
        "model": "m",
        "instructions": "Use the tools.",
        "messages": [{"role": "user", "content": "What is 1 + 2?"}],
        "tools": [ADD],
        "run_tool": runner,
    }
    return await run_agent(policy(), connection(port), **(options | overrides))


async def test_without_tools_it_is_one_plain_call() -> None:
    async with chat_server("hi") as (port, seen):
        result = await agent(port, Tools(), tools=[])

    assert (result.text, result.stop, result.iterations, result.steps) == ("hi", "answer", 1, ())
    assert "tools" not in seen[0].body
    assert [m["role"] for m in seen[0].body["messages"]] == ["system", "user"]


async def test_a_tool_call_is_run_and_its_result_goes_back_to_the_model() -> None:
    tools = Tools("3")
    async with chat_server(script=[asks(("add", '{"a": 1, "b": 2}')), says("It is 3")]) as (
        port,
        seen,
    ):
        result = await agent(port, tools)

    assert tools.calls == [("add", {"a": 1, "b": 2})]
    assert (result.text, result.stop, result.iterations) == ("It is 3", "answer", 2)
    assert [(s.name, s.result, s.is_error) for s in result.steps] == [("add", "3", False)]
    assert result.usage["total_tokens"] == 10
    assert seen[0].body["tools"][0]["function"]["name"] == "add"
    second = seen[1].body["messages"]
    assert second[-2]["tool_calls"][0]["function"]["name"] == "add"
    assert (second[-1]["role"], second[-1]["content"], second[-1]["tool_call_id"]) == (
        "tool",
        "3",
        "call_0",
    )


async def test_every_call_in_one_turn_gets_an_answer() -> None:
    tools = Tools("ok")
    turn = asks(("add", "{}"), ("add", '{"a": 1}'))
    async with chat_server(script=[turn, says("done")]) as (port, seen):
        result = await agent(port, tools)

    assert len(tools.calls) == 2 and len(result.steps) == 2
    replies = [m for m in seen[1].body["messages"] if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in replies] == ["call_0", "call_1"]


async def test_an_unknown_tool_is_reported_to_the_model_not_raised() -> None:
    tools = Tools()
    async with chat_server(script=[asks(("nope", "{}")), says("sorry")]) as (port, seen):
        result = await agent(port, tools)

    assert tools.calls == [] and result.text == "sorry"
    assert result.steps[0].is_error and "no tool named 'nope'" in result.steps[0].result
    assert "add" in seen[1].body["messages"][-1]["content"]


async def test_a_tool_that_refuses_tells_the_model_why() -> None:
    async with chat_server(script=[asks(("add", "{}")), says("ok")]) as (port, seen):
        result = await agent(port, Tools(error=ValueError("b is required")))

    assert result.steps[0].is_error
    assert seen[1].body["messages"][-1]["content"] == "error: b is required"


async def test_a_tool_that_crashes_does_not_leak_its_message() -> None:
    async with chat_server(script=[asks(("add", "{}")), says("ok")]) as (port, seen):
        result = await agent(port, Tools(error=RuntimeError("db password is hunter2")))

    assert result.steps[0].result == "error: the tool failed unexpectedly"
    assert "hunter2" not in json.dumps(seen[1].body)


async def test_arguments_that_are_not_json_are_not_run() -> None:
    tools = Tools()
    async with chat_server(script=[asks(("add", "{not json")), says("ok")]) as (port, seen):
        result = await agent(port, tools)

    assert tools.calls == []
    assert result.steps[0].is_error and "not valid JSON" in result.steps[0].result
    assert seen[1].body["messages"][-1]["role"] == "tool"


async def test_a_long_tool_result_is_cut() -> None:
    async with chat_server(script=[asks(("add", "{}")), says("ok")]) as (port, _):
        result = await agent(port, Tools("x" * 500), limits=AgentLimits(max_tool_result_chars=100))

    assert result.steps[0].result == "x" * 100 + "\n[result cut]"


async def test_it_stops_at_the_iteration_limit_without_running_the_last_tools() -> None:
    tools = Tools()
    async with chat_server(script=[asks(("add", "{}"))]) as (port, seen):
        result = await agent(port, tools, limits=AgentLimits(max_iterations=2))

    assert (result.stop, result.text, result.iterations) == ("max_iterations", "", 2)
    assert len(seen) == 2 and len(tools.calls) == 1


async def test_it_stops_when_the_token_budget_is_spent() -> None:
    tools = Tools()
    async with chat_server(script=[asks(("add", "{}"), tokens=60)]) as (port, seen):
        result = await agent(port, tools, limits=AgentLimits(max_total_tokens=50))

    assert result.stop == "max_tokens" and tools.calls == [] and len(seen) == 1
    assert result.usage["total_tokens"] == 60


async def test_it_stops_at_the_time_limit_even_if_a_tool_hangs() -> None:
    async with chat_server(script=[asks(("add", "{}")), says("late")]) as (port, _):
        result = await agent(port, Tools(wait=30), limits=AgentLimits(max_seconds=0.3))

    assert (result.stop, result.text) == ("timeout", "")
    assert result.iterations == 1


async def test_a_structured_answer_is_asked_for_once_after_the_loop_without_tools() -> None:
    fmt = {"type": "json_object"}
    script = [asks(("add", "{}")), says("It is 3"), says('{"sum": 3}')]
    async with chat_server(script=script) as (port, seen):
        result = await agent(port, Tools(), response_format=fmt)

    assert [("response_format" in c.body, "tools" in c.body) for c in seen] == [
        (False, True),
        (False, True),
        (True, False),
    ]
    assert (result.text, result.iterations, result.usage["total_tokens"]) == (
        '{"sum": 3}',
        2,
        15,
    )


@pytest.mark.parametrize(
    ("tools", "message"),
    [
        ([ToolSpec(name="bad name")], "must be 1-64"),
        ([ToolSpec(name="a"), ToolSpec(name="a")], "same name"),
        ([ToolSpec(name=f"t{i}") for i in range(65)], "at most 64"),
    ],
)
async def test_tool_names_are_checked_before_any_call(tools: list[ToolSpec], message: str) -> None:
    async with chat_server() as (port, seen):
        with pytest.raises(ValueError, match=message):
            await agent(port, Tools(), tools=tools)
    assert seen == []


async def test_a_provider_error_is_raised_with_a_hint() -> None:
    async with chat_server(status=401, raw=b'{"error": {"message": "bad key"}}') as (port, _):
        with pytest.raises(ValueError, match="rejected the key"):
            await agent(port, Tools())


async def test_a_reply_cut_off_by_the_token_limit_is_a_failure() -> None:
    cut = {"role": "assistant", "content": "", "finish_reason": "length"}
    async with chat_server(script=[cut]) as (port, _):
        with pytest.raises(ValueError, match="ran out of tokens"):
            await agent(port, Tools())


class Calls:
    def __init__(self) -> None:
        self.events: list[tuple[Any, ...]] = []

    async def started(self, index: int, messages: list[dict[str, Any]]) -> None:
        self.events.append(("started", index, [m["role"] for m in messages]))

    async def finished(self, index: int, reply: Any, error: str | None) -> None:
        self.events.append(("finished", index, reply.text if reply else None, error))


async def test_each_model_call_is_reported_with_the_conversation_it_got() -> None:
    calls = Calls()
    script = [asks(("add", '{"a": 1}')), says("It is 3")]
    async with chat_server(script=script) as (port, _):
        await agent(port, Tools(), on_model=calls)

    assert calls.events == [
        ("started", 1, ["system", "user"]),
        ("finished", 1, "", None),
        ("started", 2, ["system", "user", "ai", "tool"]),
        ("finished", 2, "It is 3", None),
    ]


async def test_a_failed_model_call_is_reported_with_its_error() -> None:
    calls = Calls()
    async with chat_server(status=401, raw=b'{"error": {"message": "bad key"}}') as (port, _):
        with pytest.raises(ValueError, match="rejected the key"):
            await agent(port, Tools(), on_model=calls)

    assert calls.events[0] == ("started", 1, ["system", "user"])
    assert calls.events[1][:3] == ("finished", 1, None) and "rejected the key" in calls.events[1][3]
