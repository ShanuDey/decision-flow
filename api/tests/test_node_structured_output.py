import json
from typing import Any

import pytest

from app.engine.llm import SchemaField, json_schema, parse_answer, response_format
from app.engine.validate import parse_graph
from tests.chat_server import chat_server
from tests.test_node_http_request import anyio_backend  # noqa: F401
from tests.test_node_prompt import CONNECTION_ID, connection, run

pytestmark = pytest.mark.anyio

FIELDS = [
    {"name": "city", "type": "string", "description": "The city named in the text"},
    {"name": "population", "type": "number"},
    {"name": "capital", "type": "boolean"},
    {"name": "size", "type": "enum", "values": ["small", "large"]},
    {"name": "tags", "type": "array"},
]
ANSWER = {"city": "Paris", "population": 2.1, "capital": True, "size": "large", "tags": ["art"]}


def flow(ask: dict[str, Any] | None = None, value: str = "{{ nodes.ask.output.city }}") -> dict:
    data = {
        "connection_id": CONNECTION_ID,
        "prompt": "Text: {{ input.who }}",
        "fields": FIELDS,
    } | (ask or {})
    return {
        "schema_version": 1,
        "variables": [],
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "data": {"inputs": [{"name": "who", "type": "string", "required": False}]},
            },
            {"id": "ask", "type": "structured_output", "data": data},
            {
                "id": "end",
                "type": "end",
                "data": {"outputs": [{"name": "city", "type": "string", "value": value}]},
            },
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "ask"},
            {"id": "e2", "source": "ask", "target": "end"},
        ],
    }


async def ask_with(reply: str, ask: dict[str, Any] | None = None):
    async with chat_server(reply) as (port, seen):
        result = await run(flow(ask), connection(port, default_model="m"))
    return result, seen


async def test_it_returns_each_field_with_its_type_and_asks_the_provider_to_enforce_it() -> None:
    result, seen = await ask_with(json.dumps(ANSWER))

    assert result.status == "succeeded", result.error
    assert result.output == {"city": "Paris"}
    sent = seen[0].body["response_format"]
    assert sent["type"] == "json_schema" and sent["json_schema"]["strict"] is True
    schema = sent["json_schema"]["schema"]
    assert (
        schema["required"] == [f["name"] for f in FIELDS]
        and schema["additionalProperties"] is False
    )
    assert schema["properties"]["city"] == {
        "type": "string",
        "description": "The city named in the text",
    }
    assert schema["properties"]["size"] == {"type": "string", "enum": ["small", "large"]}
    assert schema["properties"]["tags"] == {"type": "array", "items": {"type": "string"}}


async def test_the_fields_are_readable_by_later_nodes_with_their_types() -> None:
    graph = flow(value="{{ nodes.ask.output.size }}")
    async with chat_server(json.dumps(ANSWER)) as (port, _):
        result = await run(graph, connection(port, default_model="m"))
    assert result.output == {"city": "large"}


async def test_json_mode_asks_for_an_object_and_puts_the_schema_in_the_instructions() -> None:
    result, seen = await ask_with(json.dumps(ANSWER), {"mode": "json", "system": "Be exact."})

    assert result.status == "succeeded", result.error
    body = seen[0].body
    assert body["response_format"] == {"type": "json_object"}
    system = body["messages"][0]["content"]
    assert system.startswith("Be exact.") and "JSON Schema" in system and '"city"' in system


async def test_an_answer_in_a_code_fence_is_accepted() -> None:
    result, _ = await ask_with("```json\n" + json.dumps(ANSWER) + "\n```")
    assert result.status == "succeeded", result.error


async def test_extra_fields_in_the_answer_are_dropped() -> None:
    result, _ = await ask_with(json.dumps({**ANSWER, "note": "ignored"}))
    assert result.status == "succeeded", result.error


@pytest.mark.parametrize(
    ("reply", "message"),
    [
        ("Sure, Paris!", "did not answer with JSON"),
        ("[1, 2]", "did not answer with a JSON object"),
        (json.dumps({k: v for k, v in ANSWER.items() if k != "city"}), "city: missing"),
        (json.dumps({**ANSWER, "population": "many"}), "population: expected number"),
        (json.dumps({**ANSWER, "size": "huge"}), "size: must be one of"),
        (json.dumps({**ANSWER, "tags": [1]}), "tags: expected a list of text"),
    ],
)
async def test_an_answer_that_does_not_fit_fails_and_names_the_field(
    reply: str, message: str
) -> None:
    result, _ = await ask_with(reply)

    assert result.status == "failed" and result.error is not None
    assert result.error.node_id == "ask" and message in result.error.message


async def test_every_wrong_field_is_named_in_one_error() -> None:
    bad = {"city": 5, "population": "x", "capital": True, "size": "large", "tags": []}
    result, _ = await ask_with(json.dumps(bad))

    assert result.error is not None
    assert "city: expected string" in result.error.message
    assert "population: expected number" in result.error.message


def codes(graph: dict[str, Any]) -> list[str]:
    return sorted(i.code for i in parse_graph(graph)[1])


def test_validation_asks_for_what_is_missing() -> None:
    assert codes(flow({"connection_id": "", "prompt": " ", "fields": []}, value="done")) == [
        "missing_connection",
        "missing_fields",
        "missing_prompt",
    ]


@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ([{"name": "a b", "type": "string"}], "invalid_field_name"),
        ([{"name": "1a", "type": "string"}], "invalid_field_name"),
        ([{"name": "a", "type": "string"}, {"name": "a", "type": "number"}], "duplicate_field"),
        ([{"name": "a", "type": "object"}], "unsupported_field_type"),
    ],
)
def test_validation_refuses_fields_that_cannot_work(fields: list[dict], code: str) -> None:
    graph = flow({"fields": fields}, value="{{ nodes.ask.output.a }}")
    assert code in codes(graph)


def test_an_enum_field_needs_its_values() -> None:
    graph = flow({"fields": [{"name": "a", "type": "enum"}]})
    _, issues = parse_graph(graph)
    assert any(i.code == "schema" for i in issues)


def test_a_later_node_can_only_read_declared_fields() -> None:
    assert codes(flow(value="{{ nodes.ask.output.nope }}")) == ["unknown_reference"]
    assert codes(flow(value="{{ nodes.ask.output.city }}")) == []


def test_secrets_are_not_allowed_in_the_prompt() -> None:
    assert codes(flow({"prompt": "key {{ secrets.KEY }}"})) == ["secret_not_allowed"]


def test_the_schema_helpers_describe_every_field() -> None:
    fields = [SchemaField(**f) for f in FIELDS]
    schema = json_schema(fields)
    assert list(schema["properties"]) == [f["name"] for f in FIELDS]
    assert response_format(fields, "json") == {"type": "json_object"}
    assert parse_answer(json.dumps(ANSWER), fields)["city"] == "Paris"
