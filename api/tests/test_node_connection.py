import base64
import json
import uuid
from typing import Any

import pytest
from pydantic import SecretStr

from app.connections.catalog import BY_ID
from app.connections.types import parse_hosts, resolve
from app.engine.compiler import compile_graph
from app.engine.connections import ResolvedConnection, host_allowed
from app.engine.run_secrets import RunSecrets, referenced_connection_ids
from app.engine.runtime import run_flow
from app.engine.validate import parse_graph
from tests.conftest import service_type
from tests.recorder import Recorder
from tests.test_node_http_request import anyio_backend, flow, policy, serve  # noqa: F401

pytestmark = pytest.mark.anyio

TOKEN = "sk-live-connection-token-123"
CONNECTION_ID = str(uuid.uuid4())


def connection(headers: dict[str, str], hosts: list[str], *secrets: str) -> ResolvedConnection:
    return ResolvedConnection(
        id=CONNECTION_ID,
        name="Billing API",
        headers={k: SecretStr(v) for k, v in headers.items()},
        hosts=hosts,
        secret_values=[SecretStr(s) for s in secrets],
    )


async def run(
    call: dict[str, Any],
    connections: dict[str, ResolvedConnection],
    recorder: Recorder | None = None,
    outputs: list[dict[str, Any]] | None = None,
):
    graph, issues = parse_graph(flow({"connection_id": CONNECTION_ID, **call}, outputs))
    assert issues == [], issues
    return await run_flow(
        compile_graph(graph),
        {},
        recorder,
        secrets=RunSecrets(connections=connections),
        outbound=policy(),
    )


ECHO = [{"name": "echo", "type": "string", "value": "{{ nodes.call.output.body.body }}"}]


async def test_the_connection_header_is_sent_and_nothing_recorded_holds_the_token() -> None:
    async with serve() as (port, received):
        recorder = Recorder()
        result = await run(
            {"url": f"http://127.0.0.1:{port}/echo"},
            {CONNECTION_ID: connection({"Authorization": f"Bearer {TOKEN}"}, ["127.0.0.1"], TOKEN)},
            recorder,
        )

    assert result.status == "succeeded", result.error
    assert received[0]["headers"]["authorization"] == f"Bearer {TOKEN}"
    assert TOKEN not in str(vars(recorder)) + result.model_dump_json()
    assert recorder.node_outputs["call"]["request"]["headers"] == ["Authorization"]


async def test_a_server_that_echoes_the_header_back_is_masked_with_the_connection_name() -> None:
    async with serve() as (port, _):
        recorder = Recorder()
        result = await run(
            {"url": f"http://127.0.0.1:{port}/echo", "method": "POST", "body_type": "text"}
            | {"body": "x"},
            {CONNECTION_ID: connection({"Xkey": TOKEN}, ["127.0.0.1"], TOKEN)},
            recorder,
            [
                {
                    "name": "echo",
                    "type": "string",
                    "value": "{{ nodes.call.output.body.headers.xkey }}",
                }
            ],
        )

    assert result.status == "succeeded", result.error
    assert TOKEN not in result.model_dump_json() + str(vars(recorder))
    assert "[REDACTED:Billing API]" in result.output["echo"]


async def test_an_encoded_basic_auth_header_is_masked_too() -> None:
    kind = BY_ID["basic"]
    resolved = resolve(
        kind,
        CONNECTION_ID,
        "Billing API",
        {"username": "ada", "password": TOKEN, "hosts": "127.0.0.1"},
    )
    encoded = base64.b64encode(f"ada:{TOKEN}".encode()).decode()
    async with serve() as (port, received):
        result = await run(
            {"url": f"http://127.0.0.1:{port}/echo"}, {CONNECTION_ID: resolved}, outputs=ECHO
        )

    assert received[0]["headers"]["authorization"] == f"Basic {encoded}"
    assert encoded not in result.model_dump_json() and TOKEN not in result.model_dump_json()


async def test_a_host_the_connection_does_not_allow_is_refused_before_anything_is_sent() -> None:
    async with serve() as (port, received):
        result = await run(
            {"url": f"http://127.0.0.1:{port}/echo"},
            {CONNECTION_ID: connection({"Authorization": f"Bearer {TOKEN}"}, ["api.example.com"])},
        )

    assert result.status == "failed" and received == []
    message = result.error.message
    assert "Billing API" in message and "api.example.com" in message and "127.0.0.1" in message
    assert TOKEN not in result.model_dump_json()


async def test_a_header_set_in_the_node_wins_over_the_connection() -> None:
    async with serve() as (port, received):
        result = await run(
            {
                "url": f"http://127.0.0.1:{port}/echo",
                "headers": {"authorization": "Token mine"},
            },
            {CONNECTION_ID: connection({"Authorization": f"Bearer {TOKEN}"}, ["127.0.0.1"], TOKEN)},
        )

    assert result.status == "succeeded", result.error
    assert received[0]["headers"]["authorization"] == "Token mine"


async def test_a_connection_that_was_not_loaded_fails_the_node_clearly() -> None:
    async with serve() as (port, received):
        result = await run({"url": f"http://127.0.0.1:{port}/echo"}, {})

    assert result.status == "failed" and received == []
    assert "connection is not available" in result.error.message


def test_a_node_without_a_connection_is_unchanged_and_lists_no_ids() -> None:
    graph, _ = parse_graph(flow({"url": "https://api.example.com"}))
    assert graph is not None and referenced_connection_ids(graph) == set()


def test_the_graph_lists_the_connections_its_nodes_use() -> None:
    graph, _ = parse_graph(flow({"url": "https://api.example.com", "connection_id": CONNECTION_ID}))
    assert graph is not None and referenced_connection_ids(graph) == {CONNECTION_ID}


def test_an_id_that_is_not_a_uuid_is_flagged_at_validation() -> None:
    _, issues = parse_graph(flow({"url": "https://api.example.com", "connection_id": "nope"}))
    assert [(i.code, i.field) for i in issues] == [("invalid_connection", "data.connection_id")]


@pytest.mark.parametrize(
    ("host", "patterns", "allowed"),
    [
        ("api.example.com", ["api.example.com"], True),
        ("API.Example.com.", ["api.example.com"], True),
        ("other.example.com", ["api.example.com"], False),
        ("evil-api.example.com", ["api.example.com"], False),
        ("a.example.com", ["*.example.com"], True),
        ("a.b.example.com", ["*.example.com"], True),
        ("example.com", ["*.example.com"], False),
        ("badexample.com", ["*.example.com"], False),
        ("anything.test", [], False),
    ],
)
def test_host_matching(host: str, patterns: list[str], allowed: bool) -> None:
    assert host_allowed(host, patterns) is allowed


def test_each_type_builds_its_header_and_hosts() -> None:
    bearer = resolve(BY_ID["bearer"], "i", "n", {"token": TOKEN, "hosts": "A.com, *.b.com"})
    assert bearer.headers["Authorization"].get_secret_value() == f"Bearer {TOKEN}"
    assert bearer.hosts == ["a.com", "*.b.com"]

    custom = resolve(
        BY_ID["api_key_header"],
        "i",
        "n",
        {"header_name": "X-Api-Key", "api_key": TOKEN, "hosts": "a.com"},
    )
    assert {k: v.get_secret_value() for k, v in custom.headers.items()} == {"X-Api-Key": TOKEN}

    service = resolve(service_type(fixed_hosts=["api.acme.test"]), "i", "n", {"api_key": TOKEN})
    assert service.hosts == ["api.acme.test"]
    assert json.dumps([s.get_secret_value() for s in service.secret_values]).count(TOKEN) == 2


@pytest.mark.parametrize(
    "raw", ["", " , ", "https://a.com", "a.com/path", "a.com:8080", "a b.com", "-a.com"]
)
def test_bad_hosts_are_refused(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_hosts(raw)


def test_the_openai_card_allows_only_the_host_of_its_base_url() -> None:
    kind = BY_ID["openai_compatible"]
    default = resolve(kind, "i", "n", {"api_key": TOKEN})
    assert default.hosts == ["api.openai.com"]
    custom = resolve(
        kind, "i", "n", {"api_key": TOKEN, "base_url": "https://Proxy.Example.com:8443/v1"}
    )
    assert custom.hosts == ["proxy.example.com"]
    assert custom.headers["Authorization"].get_secret_value() == f"Bearer {TOKEN}"
