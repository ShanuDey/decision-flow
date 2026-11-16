import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from app.engine.compiler import compile_graph
from app.engine.run_secrets import RunSecrets
from app.engine.runtime import run_flow
from app.engine.validate import parse_graph
from app.security.ssrf import OutboundPolicy
from app.templates.service import load_templates
from tests.recorder import Recorder

SECRET = "sk_live_abcdefghij123"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def policy(**overrides: object) -> OutboundPolicy:
    values = {"allow_private": True, "max_bytes": 100_000, "timeout_seconds": 5, **overrides}
    return OutboundPolicy(**values)  # type: ignore[arg-type]


@asynccontextmanager
async def serve() -> AsyncIterator[tuple[int, list[dict[str, Any]]]]:
    """Answers /echo with what it received; other paths give fixed answers."""
    received: list[dict[str, Any]] = []

    async def reply(writer: asyncio.StreamWriter, status: str, ctype: str, body: bytes) -> None:
        head = f"HTTP/1.1 {status}\r\nContent-Type: {ctype}\r\nContent-Length: {len(body)}\r\n"
        writer.write(f"{head}Connection: close\r\n\r\n".encode() + body)
        await writer.drain()
        writer.close()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        head = (await reader.readuntil(b"\r\n\r\n")).decode().split("\r\n")
        method, target, _ = head[0].split()
        headers = {k.lower(): v for k, v in (h.split(": ", 1) for h in head[1:] if ": " in h)}
        body = await reader.readexactly(int(headers.get("content-length", "0")))
        received.append({"method": method, "target": target, "headers": headers, "body": body})
        path = urlsplit(target).path
        if path == "/echo":
            payload = {
                "method": method,
                "target": target,
                "headers": headers,
                "body": body.decode(),
            }
            await reply(writer, "200 OK", "application/json", json.dumps(payload).encode())
        elif path.startswith("/users/"):
            if path == "/users/99":
                await reply(writer, "404 Not Found", "application/json", b"{}")
            else:
                user = {"name": "Ada", "email": "ada@example.test", "company": {"name": "Acme"}}
                await reply(writer, "200 OK", "application/json", json.dumps(user).encode())
        elif path == "/missing":
            await reply(writer, "404 Not Found", "application/json", b'{"error": "nope"}')
        elif path == "/text":
            await reply(writer, "200 OK", "text/plain", b"hello")
        elif path == "/redirect":
            writer.write(b"HTTP/1.1 302 Found\r\nLocation: /echo\r\nContent-Length: 0\r\n\r\n")
            await writer.drain()
            writer.close()
        elif path == "/big":
            await reply(writer, "200 OK", "text/plain", b"x" * 5000)
        elif path == "/slow":
            await asyncio.sleep(3)
            await reply(writer, "200 OK", "text/plain", b"late")
        else:
            await reply(writer, "200 OK", "text/plain", b"ok")

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    try:
        yield server.sockets[0].getsockname()[1], received
    finally:
        server.close()
        await server.wait_closed()


def flow(call: dict[str, Any], outputs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "variables": [],
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "data": {
                    "inputs": [
                        {"name": "amount", "type": "number", "required": False},
                        {"name": "name", "type": "string", "required": False},
                    ]
                },
            },
            {"id": "call", "type": "http_request", "data": call},
            {"id": "end", "type": "end", "data": {"outputs": outputs or []}},
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "call"},
            {"id": "e2", "source": "call", "target": "end"},
        ],
    }


def codes(raw: dict[str, Any], **kwargs: Any) -> list[str]:
    return [i.code for i in parse_graph(raw, **kwargs)[1]]


async def run(
    raw: dict[str, Any],
    payload: dict[str, Any] | None = None,
    *,
    secrets: dict[str, str] | None = None,
    outbound: OutboundPolicy | None = None,
    recorder: Recorder | None = None,
):
    graph, issues = parse_graph(raw)
    assert issues == [], issues
    return await run_flow(
        compile_graph(graph),
        payload or {},
        recorder,
        secrets=RunSecrets(values=secrets or {}),
        outbound=outbound or policy(),
    )


def echoed(recorder: Recorder) -> dict[str, Any]:
    """What the /echo server saw: method, target, headers and the raw body text."""
    return recorder.node_outputs["call"]["body"]


def test_secrets_are_allowed_in_headers_query_and_every_body_type_but_not_the_url() -> None:
    secret = "{{ secrets.API_KEY }}"
    for data in (
        {"url": "https://x.test", "headers": {"Authorization": f"Bearer {secret}"}},
        {"url": "https://x.test", "query": {"key": secret}},
        {"url": "https://x.test", "method": "POST", "body_type": "json", "body": {"a": [secret]}},
        {"url": "https://x.test", "method": "POST", "body_type": "form", "body": {"k": secret}},
        {"url": "https://x.test", "method": "POST", "body_type": "text", "body": secret},
    ):
        assert codes(flow(data)) == [], data

    assert codes(flow({"url": f"https://x.test/{secret}"})) == ["secret_not_allowed"]
    assert codes(flow({"url": secret})) == ["secret_not_allowed"]


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({}, "missing_url"),
        ({"url": "ftp://x.test"}, "invalid_url"),
        ({"url": "x.test/path"}, "invalid_url"),
        ({"url": "https://x.test", "headers": {"Bad Header": "v"}}, "invalid_header_name"),
        ({"url": "https://x.test", "query": {" ": "v"}}, "invalid_query_name"),
        ({"url": "https://x.test", "body_type": "json", "body": {}}, "body_not_allowed"),
        ({"url": "https://x.test", "body": {"a": 1}}, "invalid_body"),
        ({"url": "https://x.test", "method": "POST", "body_type": "json"}, "invalid_body"),
        (
            {"url": "https://x.test", "method": "POST", "body_type": "form", "body": {"a": 1}},
            "invalid_body",
        ),
        (
            {"url": "https://x.test", "method": "POST", "body_type": "text", "body": {"a": "b"}},
            "invalid_body",
        ),
    ],
)
def test_settings_problems_are_named(data: dict[str, Any], expected: str) -> None:
    assert codes(flow(data)) == [expected]


def test_a_templated_url_is_not_checked_for_its_scheme() -> None:
    raw = flow({"url": "{{ input.name }}/path"})

    assert codes(raw) == []


def test_a_later_node_can_read_the_response_but_only_from_upstream_and_only_its_output() -> None:
    out = [{"name": "v", "type": "string", "value": "{{ nodes.call.output.body.x }}"}]
    assert codes(flow({"url": "https://x.test"}, out)) == []

    wrong = [{"name": "v", "type": "string", "value": "{{ nodes.call.status }}"}]
    assert codes(flow({"url": "https://x.test"}, wrong)) == ["unknown_reference"]

    early = flow({"url": "https://x.test/{{ nodes.end.output.x }}"})
    assert codes(early) == ["not_upstream"]


def test_the_node_can_be_turned_off_for_a_server() -> None:
    raw = flow({"url": "https://x.test"})

    assert codes(raw, disabled_types={"http_request"}) == ["node_disabled"]
    assert codes(raw, disabled_types={"assign"}) == []
    graph, issues = parse_graph(raw, disabled_types={"http_request"})
    assert graph is None and issues[0].node_id == "call"


@pytest.mark.anyio
async def test_a_get_with_query_values_is_encoded_and_the_response_is_usable_downstream() -> None:
    async with serve() as (port, received):
        raw = flow(
            {
                "url": f"http://127.0.0.1:{port}/echo?fixed=1",
                "query": {"q": "{{ input.name }}", "n": "{{ input.amount }}"},
            },
            [
                {
                    "name": "method",
                    "type": "string",
                    "value": "{{ nodes.call.output.body.method }}",
                },
                {"name": "status", "type": "number", "value": "{{ nodes.call.output.status }}"},
            ],
        )
        recorder = Recorder()
        result = await run(raw, {"name": "a&b=c d", "amount": 7}, recorder=recorder)

    assert result.status == "succeeded", result.error
    assert result.output == {"method": "GET", "status": 200}
    query = parse_qs(urlsplit(received[0]["target"]).query)
    assert query == {"fixed": ["1"], "q": ["a&b=c d"], "n": ["7"]}
    output = recorder.node_outputs["call"]
    assert output["ok"] is True and output["headers"]["content-type"] == "application/json"
    assert output["request"] == {
        "method": "GET",
        "url": f"http://127.0.0.1:{port}/echo?fixed=1",
        "query": ["q", "n"],
        "headers": [],
    }


@pytest.mark.anyio
async def test_a_json_body_keeps_numbers_and_cannot_be_broken_out_of_by_input() -> None:
    nasty = '", "admin": true, "x": "'
    async with serve() as (port, _):
        raw = flow(
            {
                "method": "POST",
                "url": f"http://127.0.0.1:{port}/echo",
                "body_type": "json",
                "body": {
                    "amount": "{{ input.amount }}",
                    "name": "{{ input.name }}",
                    "list": ["{{ input.name }}", 1],
                },
            }
        )
        recorder = Recorder()
        await run(raw, {"amount": 5, "name": nasty}, recorder=recorder)

    sent = json.loads(echoed(recorder)["body"])
    assert sent == {"amount": 5, "name": nasty, "list": [nasty, 1]}
    assert echoed(recorder)["headers"]["content-type"] == "application/json"


@pytest.mark.anyio
async def test_a_form_body_is_url_encoded_field_by_field() -> None:
    async with serve() as (port, _):
        raw = flow(
            {
                "method": "POST",
                "url": f"http://127.0.0.1:{port}/echo",
                "body_type": "form",
                "body": {"name": "{{ input.name }}", "plain": "x"},
            }
        )
        recorder = Recorder()
        await run(raw, {"name": "a&admin=1 é"}, recorder=recorder)

    sent = echoed(recorder)
    assert parse_qs(sent["body"]) == {"name": ["a&admin=1 é"], "plain": ["x"]}
    assert sent["headers"]["content-type"] == "application/x-www-form-urlencoded"


@pytest.mark.anyio
async def test_a_text_body_is_sent_as_is_and_an_explicit_content_type_wins() -> None:
    async with serve() as (port, _):
        plain = flow(
            {
                "method": "PUT",
                "url": f"http://127.0.0.1:{port}/echo",
                "body_type": "text",
                "body": "<a>{{ input.name }}</a>",
            }
        )
        custom = flow(
            {
                "method": "PUT",
                "url": f"http://127.0.0.1:{port}/echo",
                "headers": {"content-type": "application/xml"},
                "body_type": "text",
                "body": "<a/>",
            }
        )
        first, second = Recorder(), Recorder()
        await run(plain, {"name": "hi"}, recorder=first)
        await run(custom, recorder=second)

    assert echoed(first)["body"] == "<a>hi</a>"
    assert echoed(first)["headers"]["content-type"] == "text/plain; charset=utf-8"
    assert echoed(second)["headers"]["content-type"] == "application/xml"


@pytest.mark.anyio
async def test_a_secret_reaches_the_server_and_nothing_that_is_recorded() -> None:
    async with serve() as (port, received):
        raw = flow(
            {
                "method": "POST",
                "url": f"http://127.0.0.1:{port}/echo",
                "headers": {"Authorization": "Bearer {{ secrets.API_KEY }}"},
                "query": {"key": "{{ secrets.API_KEY }}"},
                "body_type": "json",
                "body": {"token": "{{ secrets.API_KEY }}"},
            },
            [{"name": "echo", "type": "string", "value": "{{ nodes.call.output.body.body }}"}],
        )
        recorder = Recorder()
        result = await run(raw, secrets={"API_KEY": SECRET}, recorder=recorder)

    assert result.status == "succeeded", result.error
    (request,) = received
    assert request["headers"]["authorization"] == f"Bearer {SECRET}"
    assert f"key={SECRET}" in request["target"]
    assert json.loads(request["body"]) == {"token": SECRET}
    everything = str(vars(recorder)) + result.model_dump_json()
    assert SECRET not in everything
    assert "[REDACTED:API_KEY]" in str(recorder.node_outputs["call"]["body"])
    assert "[REDACTED:API_KEY]" in result.output["echo"]
    assert recorder.node_outputs["call"]["request"]["headers"] == [
        "Authorization",
        "Content-Type",
    ]


@pytest.mark.anyio
async def test_a_non_2xx_answer_is_data_and_can_be_made_a_failure() -> None:
    async with serve() as (port, _):
        raw = flow({"url": f"http://127.0.0.1:{port}/missing"})
        recorder = Recorder()
        ok = await run(raw, recorder=recorder)
        raw["nodes"][1]["data"]["fail_on_error_status"] = True
        failed = await run(raw)

    assert ok.status == "succeeded"
    assert recorder.node_outputs["call"]["status"] == 404
    assert recorder.node_outputs["call"]["ok"] is False
    assert recorder.node_outputs["call"]["body"] == {"error": "nope"}
    assert failed.status == "failed" and failed.error.node_id == "call"
    assert "HTTP 404" in failed.error.message


@pytest.mark.anyio
async def test_a_text_response_and_a_redirect_come_back_as_data() -> None:
    async with serve() as (port, received):
        text, redirect = Recorder(), Recorder()
        await run(flow({"url": f"http://127.0.0.1:{port}/text"}), recorder=text)
        await run(flow({"url": f"http://127.0.0.1:{port}/redirect"}), recorder=redirect)

    assert text.node_outputs["call"]["body"] == "hello"
    assert redirect.node_outputs["call"]["status"] == 302
    assert redirect.node_outputs["call"]["headers"]["location"] == "/echo"
    assert [r["target"] for r in received] == ["/text", "/redirect"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("url", "allow_private", "code"),
    [
        ("https://127.0.0.1:1/", False, "blocked_destination"),
        ("http://169.254.169.254/latest/meta-data/", True, "blocked_destination"),
        ("https://0.0.0.0/", True, "blocked_destination"),
        ("http://127.0.0.1/", False, "scheme_not_allowed"),
        ("file:///etc/passwd", True, "scheme_not_allowed"),
    ],
)
async def test_an_address_the_guard_refuses_fails_the_node_with_a_named_reason(
    url: str, allow_private: bool, code: str
) -> None:
    raw = flow({"url": "{{ input.name }}"})
    result = await run(raw, {"name": url}, outbound=policy(allow_private=allow_private))

    assert result.status == "failed" and result.error.node_id == "call"
    assert f"({code})" in result.error.message


@pytest.mark.anyio
async def test_a_big_response_and_a_slow_server_fail_the_node() -> None:
    async with serve() as (port, _):
        big = await run(
            flow({"url": f"http://127.0.0.1:{port}/big"}), outbound=policy(max_bytes=1000)
        )
        slow = await run(
            flow({"url": f"http://127.0.0.1:{port}/slow", "timeout_seconds": 1}),
            outbound=policy(timeout_seconds=10),
        )

    assert "(response_too_large)" in big.error.message
    assert "(timeout)" in slow.error.message


@pytest.mark.anyio
async def test_the_node_timeout_cannot_exceed_the_server_limit() -> None:
    async with serve() as (port, _):
        result = await run(
            flow({"url": f"http://127.0.0.1:{port}/slow", "timeout_seconds": 60}),
            outbound=policy(timeout_seconds=1),
        )

    assert "(timeout)" in result.error.message


@pytest.mark.anyio
async def test_a_template_that_cannot_render_names_the_field() -> None:
    raw = flow({"url": "http://127.0.0.1:1/{{ input.name }}"})
    result = await run(raw, {})

    assert result.status == "failed"
    assert result.error.message.startswith("url: input.name is not set")


@pytest.mark.anyio
async def test_without_an_outbound_policy_the_node_refuses_to_run() -> None:
    graph, _ = parse_graph(flow({"url": "http://127.0.0.1:1/"}))
    result = await run_flow(compile_graph(graph), {})

    assert result.status == "failed"
    assert "not configured" in result.error.message


@pytest.mark.anyio
async def test_the_api_lookup_template_reads_the_response_and_fails_on_an_error_status() -> None:
    template = next(t for t in load_templates() if t.id == "api-lookup")
    async with serve() as (port, received):
        raw = json.loads(json.dumps(template.draft))
        call = next(n for n in raw["nodes"] if n["id"] == "lookup")
        call["data"]["url"] = f"http://127.0.0.1:{port}/users/{{{{ input.user_id }}}}"
        found = await run(raw, {"user_id": 3})
        missing = await run(raw, {"user_id": 99})

    assert found.status == "succeeded", found.error
    assert found.output == {
        "name": "Ada",
        "email": "ada@example.test",
        "company": "Acme",
        "status": 200,
    }
    assert [r["target"] for r in received] == ["/users/3", "/users/99"]
    assert missing.status == "failed" and missing.error.node_id == "lookup"
    assert "HTTP 404" in missing.error.message


def test_the_api_lookup_template_calls_a_public_https_address() -> None:
    template = next(t for t in load_templates() if t.id == "api-lookup")
    call = next(n for n in template.draft["nodes"] if n["id"] == "lookup")

    assert call["data"]["url"].startswith("https://")
    assert template.node_types == ["end", "http_request", "start"]


@pytest.mark.parametrize(
    "name", ["Host", "Content-Length", "transfer-encoding", "Connection", "Upgrade", "TE"]
)
def test_headers_the_server_sets_are_refused_at_validation(name: str) -> None:
    raw = flow({"url": "https://x.test", "headers": {name: "x"}})

    assert codes(raw) == ["reserved_header"]


@pytest.mark.anyio
async def test_a_template_cannot_multiply_a_big_input_into_a_huge_request() -> None:
    big = "x" * 40_000
    leaves = {f"k{i}": "{{ input.name }}" for i in range(500)}
    async with serve() as (port, received):
        body = flow(
            {
                "method": "POST",
                "url": f"http://127.0.0.1:{port}/echo",
                "body_type": "json",
                "body": leaves,
            }
        )
        form = flow(
            {
                "method": "POST",
                "url": f"http://127.0.0.1:{port}/echo",
                "body_type": "form",
                "body": leaves,
            }
        )
        query = flow({"url": f"http://127.0.0.1:{port}/echo", "query": leaves})
        results = [
            await run(raw, {"name": big}, outbound=policy(max_bytes=100_000))
            for raw in (body, form, query)
        ]

    for result in results:
        assert result.status == "failed" and result.error.node_id == "call"
        assert "larger than the allowed size" in result.error.message
    assert received == []


@pytest.mark.anyio
async def test_a_request_within_the_size_limit_still_goes_out() -> None:
    async with serve() as (port, received):
        raw = flow(
            {
                "method": "POST",
                "url": f"http://127.0.0.1:{port}/echo",
                "body_type": "json",
                "body": {"a": "{{ input.name }}", "b": "{{ input.name }}"},
            }
        )
        result = await run(raw, {"name": "x" * 1000}, outbound=policy(max_bytes=100_000))

    assert result.status == "succeeded" and len(received) == 1
