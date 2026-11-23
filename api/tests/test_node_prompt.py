from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.connections.catalog import BY_ID
from app.connections.types import resolve
from app.engine.compiler import compile_graph
from app.engine.connections import ResolvedConnection
from app.engine.llm import chat as chat_module
from app.engine.llm.chat import _reply
from app.engine.run_secrets import RunSecrets
from app.engine.runtime import run_flow
from app.engine.validate import parse_graph
from tests.chat_server import chat_server
from tests.recorder import Recorder
from tests.test_node_http_request import anyio_backend, policy  # noqa: F401

pytestmark = pytest.mark.anyio

CONNECTION_ID = "5f0a2c1e-7b3d-4e6a-9c8f-1d2e3f4a5b6c"
TOKEN = "test-token-for-the-prompt-node"


def flow(ask: dict[str, Any] | None = None) -> dict[str, Any]:
    data = {"connection_id": CONNECTION_ID, "prompt": "Say hi to {{ input.who }}"} | (ask or {})
    return {
        "schema_version": 1,
        "variables": [],
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "data": {"inputs": [{"name": "who", "type": "string", "required": False}]},
            },
            {"id": "ask", "type": "prompt", "data": data},
            {
                "id": "end",
                "type": "end",
                "data": {
                    "outputs": [
                        {"name": "answer", "type": "string", "value": "{{ nodes.ask.output.text }}"}
                    ]
                },
            },
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "ask"},
            {"id": "e2", "source": "ask", "target": "end"},
        ],
    }


def connection(port: int, **values: str) -> ResolvedConnection:
    return resolve(
        BY_ID["openai_compatible"],
        CONNECTION_ID,
        "Local model",
        {"api_key": TOKEN, "base_url": f"http://127.0.0.1:{port}/v1", **values},
    )


async def run(
    graph: dict[str, Any], conn: ResolvedConnection | None, recorder: Recorder | None = None
):
    parsed, issues = parse_graph(graph)
    assert issues == [], issues
    assert parsed is not None
    secrets = RunSecrets(connections={CONNECTION_ID: conn} if conn else {})
    return await run_flow(
        compile_graph(parsed), {"who": "Ada"}, recorder, secrets=secrets, outbound=policy()
    )


async def test_it_sends_the_prompt_and_returns_the_text() -> None:
    async with chat_server("Hello Ada") as (port, seen):
        recorder = Recorder()
        ask = {"system": "Be brief.", "temperature": 0.2, "max_tokens": 50}
        result = await run(flow(ask), connection(port, default_model="some/model"), recorder)

    assert result.status == "succeeded", result.error
    assert result.output == {"answer": "Hello Ada"}
    (call,) = seen
    assert call.target == "/v1/chat/completions"
    assert call.headers["authorization"] == f"Bearer {TOKEN}"
    assert call.body["model"] == "some/model"
    assert [(m["role"], m["content"]) for m in call.body["messages"]] == [
        ("system", "Be brief."),
        ("user", "Say hi to Ada"),
    ]
    assert call.body["temperature"] == 0.2 and call.body["max_completion_tokens"] == 50
    output = recorder.node_outputs["ask"]
    assert output["model"] == "served-model" and output["finish_reason"] == "stop"
    assert output["usage"] == {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}
    assert TOKEN not in str(vars(recorder)) + result.model_dump_json()


async def test_a_model_in_the_node_wins_over_the_connection_default() -> None:
    async with chat_server() as (port, seen):
        graph = flow({"model": "{{ input.who }}-model"})
        result = await run(graph, connection(port, default_model="d"))

    assert result.status == "succeeded", result.error
    assert seen[0].body["model"] == "Ada-model"


async def test_it_needs_a_model_from_the_node_or_the_connection() -> None:
    async with chat_server() as (port, seen):
        result = await run(flow(), connection(port))

    assert result.status == "failed" and result.error is not None
    assert result.error.node_id == "ask" and "no model" in result.error.message
    assert seen == []


@pytest.mark.parametrize(
    ("status", "text"),
    [
        (401, "the provider rejected the key (HTTP 401): bad key"),
        (402, "the provider needs payment or credit (HTTP 402): bad key"),
        (429, "wait and retry (HTTP 429): bad key"),
        (500, "the provider answered with an error (HTTP 500): bad key"),
    ],
)
async def test_a_provider_error_says_what_to_do_and_quotes_the_provider(
    status: int, text: str
) -> None:
    body = b'{"error": {"message": "bad key"}}'
    async with chat_server(status=status, raw=body) as (port, _):
        result = await run(flow(), connection(port, default_model="m"))

    assert result.status == "failed" and result.error is not None
    assert text in result.error.message


async def test_a_reply_that_is_not_a_chat_completion_is_refused() -> None:
    async with chat_server(raw=b'{"hello": "world"}') as (port, _):
        result = await run(flow(), connection(port, default_model="m"))

    assert result.status == "failed" and result.error is not None
    assert "not a chat completion" in result.error.message


async def test_a_connection_without_a_base_url_is_explained() -> None:
    bearer = resolve(BY_ID["bearer"], CONNECTION_ID, "Plain", {"token": TOKEN, "hosts": "x.test"})
    result = await run(flow(), bearer)

    assert result.status == "failed" and result.error is not None
    assert "has no base URL" in result.error.message


async def test_the_key_goes_only_to_the_hosts_the_connection_allows() -> None:
    async with chat_server() as (port, seen):
        conn = connection(port, default_model="m").model_copy(update={"hosts": ["other.test"]})
        result = await run(flow(), conn)

    assert result.status == "failed" and result.error is not None
    assert "may only call other.test" in result.error.message
    assert seen == []


async def test_a_missing_connection_fails_before_anything_is_sent() -> None:
    async with chat_server() as (_, seen):
        result = await run(flow(), None)

    assert result.status == "failed" and result.error is not None
    assert "connection is not available" in result.error.message
    assert seen == []


def test_validation_asks_for_a_connection_and_a_prompt() -> None:
    _, issues = parse_graph(flow({"connection_id": "", "prompt": " "}))
    assert sorted(i.code for i in issues) == ["missing_connection", "missing_prompt"]
    _, issues = parse_graph(flow({"connection_id": "nope"}))
    assert [i.code for i in issues] == ["invalid_connection"]


def test_templates_may_read_the_connection_but_not_secrets() -> None:
    ok, issues = parse_graph(flow({"model": "{{ connection.default_model }}"}))
    assert ok is not None, issues
    _, issues = parse_graph(flow({"prompt": "key {{ secrets.KEY }}"}))
    assert [i.code for i in issues] == ["secret_not_allowed"]


def test_a_later_node_cannot_read_an_output_the_node_does_not_have() -> None:
    graph = flow()
    graph["nodes"][2]["data"]["outputs"][0]["value"] = "{{ nodes.ask.output.nope }}"
    _, issues = parse_graph(graph)
    assert [i.code for i in issues] == ["unknown_reference"]


async def test_options_that_are_not_set_are_not_sent() -> None:
    async with chat_server() as (port, seen):
        result = await run(flow(), connection(port, default_model="m"))

    assert result.status == "succeeded", result.error
    sent = seen[0].body
    assert set(sent) <= {"model", "messages", "stream"}


async def test_a_query_in_the_base_url_stays_a_query_and_the_endpoint_stays_the_path() -> None:
    async with chat_server() as (port, seen):
        base = f"http://127.0.0.1:{port}/openai?api-version=2024-01-01"
        conn = connection(port, default_model="m").model_copy(
            update={"values": {"base_url": base, "default_model": "m"}}
        )
        result = await run(flow(), conn)

    assert result.status == "succeeded", result.error
    assert seen[0].target == "/openai/chat/completions?api-version=2024-01-01"


async def test_a_base_url_cannot_swallow_the_endpoint_with_a_question_mark_or_hash() -> None:
    async with chat_server() as (port, seen):
        for tail in ("/admin/do?", "/admin/do#"):
            conn = connection(port, default_model="m").model_copy(
                update={
                    "values": {"base_url": f"http://127.0.0.1:{port}{tail}", "default_model": "m"}
                }
            )
            result = await run(flow(), conn)
            assert result.status == "succeeded", result.error

    assert [call.target for call in seen] == ["/admin/do/chat/completions"] * 2


async def test_the_key_never_goes_to_a_host_the_policy_blocks() -> None:
    conn = connection(1).model_copy(
        update={
            "values": {"base_url": "http://169.254.169.254/v1", "default_model": "m"},
            "hosts": ["169.254.169.254"],
        }
    )
    result = await run(flow(), conn)

    assert result.status == "failed" and result.error is not None
    assert "blocked_destination" in result.error.message
    assert "169.254" not in result.error.message.split(":", 1)[1]


async def test_a_provider_error_that_echoes_the_key_is_masked() -> None:
    body = ('{"error": {"message": "bad key ' + TOKEN + '"}}').encode()
    async with chat_server(status=401, raw=body) as (port, _):
        recorder = Recorder()
        result = await run(flow(), connection(port, default_model="m"), recorder)

    assert result.status == "failed" and result.error is not None
    assert TOKEN not in result.error.message + result.model_dump_json() + str(vars(recorder))


async def test_a_secret_cut_in_half_by_the_message_limit_is_still_masked() -> None:
    body = ('{"error": {"message": "' + "x" * 285 + " Bearer " + TOKEN + '"}}').encode()
    async with chat_server(status=400, raw=body) as (port, _):
        result = await run(flow(), connection(port, default_model="m"))

    assert result.status == "failed" and result.error is not None
    assert TOKEN[:6] not in result.error.message


async def test_a_header_on_the_connection_cannot_change_where_the_request_says_it_is_going() -> (
    None
):
    async with chat_server() as (port, seen):
        base = connection(port, default_model="m")
        headers = {**base.headers, "Host": SecretStr("internal.example")}
        result = await run(flow(), base.model_copy(update={"headers": headers}))

    assert result.status == "succeeded", result.error
    assert seen[0].headers["host"] == f"127.0.0.1:{port}"


async def test_the_host_check_uses_the_name_that_will_be_dialed() -> None:
    conn = connection(1, default_model="m").model_copy(
        update={
            "values": {"base_url": "https://allowed.test\uff0eevil.test/v1", "default_model": "m"},
            "hosts": ["allowed.test"],
        }
    )
    result = await run(flow(), conn)

    assert result.status == "failed" and result.error is not None
    assert "may only call allowed.test" in result.error.message


async def test_the_servers_own_openai_settings_are_never_sent_to_the_providers_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_ORG_ID", "org-of-the-operator")
    monkeypatch.setenv("OPENAI_PROJECT_ID", "project-of-the-operator")
    monkeypatch.setenv("OPENAI_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("OPENAI_API_KEY", "key-of-the-operator")
    async with chat_server() as (port, seen):
        result = await run(flow(), connection(port, default_model="m"))

    assert result.status == "succeeded", result.error
    sent = seen[0].headers
    assert sent["authorization"] == f"Bearer {TOKEN}"
    assert not [name for name in sent if name.startswith("openai-")]


EMPTY_CUT_OFF = (
    b'{"id": "x", "object": "chat.completion", "model": "m", "choices": '
    b'[{"index": 0, "message": {"role": "assistant", "content": ""}, "finish_reason": "%s"}]}'
)


async def test_an_empty_answer_cut_off_by_max_tokens_is_an_error_not_a_blank_reply() -> None:
    async with chat_server(raw=EMPTY_CUT_OFF % b"length") as (port, _):
        result = await run(flow({"max_tokens": 5}), connection(port, default_model="m"))

    assert result.status == "failed" and result.error is not None
    assert "ran out of tokens" in result.error.message


async def test_an_empty_answer_that_ended_normally_is_still_a_reply() -> None:
    async with chat_server(raw=EMPTY_CUT_OFF % b"stop") as (port, _):
        result = await run(flow(), connection(port, default_model="m"))

    assert result.status == "succeeded", result.error
    assert result.output == {"answer": ""}


async def test_an_unexpected_error_is_named_and_not_called_a_bad_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("internal detail")

    monkeypatch.setattr(ChatOpenAI, "ainvoke", boom)
    async with chat_server() as (port, _):
        result = await run(flow(), connection(port, default_model="m"))

    assert result.status == "failed" and result.error is not None
    assert result.error.message == "the model call failed unexpectedly (RuntimeError)"


async def test_a_client_that_cannot_be_built_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> None:
        raise ValueError("internal detail")

    monkeypatch.setattr(chat_module, "ChatOpenAI", refuse)
    async with chat_server() as (port, seen):
        result = await run(flow(), connection(port, default_model="m"))

    assert result.status == "failed" and result.error is not None
    assert result.error.message == "the model call could not be set up (ValueError)"
    assert seen == []


def test_token_counts_come_from_either_place_the_library_puts_them() -> None:
    counted = AIMessage(
        content="x", usage_metadata={"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}
    )
    assert _reply(counted, "m").usage == {
        "prompt_tokens": 3,
        "completion_tokens": 2,
        "total_tokens": 5,
    }
    reported = AIMessage(
        content="x", response_metadata={"token_usage": {"prompt_tokens": 7, "total_tokens": 9}}
    )
    assert _reply(reported, "m").usage == {"prompt_tokens": 7, "total_tokens": 9}
    assert _reply(AIMessage(content="x"), "m").usage == {}
