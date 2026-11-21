import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest

from app.security.ssrf import OutboundPolicy
from app.security.transport import BlockedRequest, GuardedTransport, guarded_client
from tests.test_node_http_request import anyio_backend  # noqa: F401

pytestmark = pytest.mark.anyio


def policy(**overrides: object) -> OutboundPolicy:
    values = {"allow_private": True, "max_bytes": 1000, "timeout_seconds": 5, **overrides}
    return OutboundPolicy(**values)  # type: ignore[arg-type]


def reply(status: str = "200 OK", body: bytes = b"ok", *headers: str) -> bytes:
    lines = [f"HTTP/1.1 {status}", f"Content-Length: {len(body)}", "Connection: close", *headers]
    return ("\r\n".join(lines) + "\r\n\r\n").encode() + body


@asynccontextmanager
async def serve(routes: dict[str, bytes]) -> AsyncIterator[tuple[int, list[dict[str, str]]]]:
    """Answers each path with the raw response given for it, and records the request headers."""
    seen: list[dict[str, str]] = []

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        head = (await reader.readuntil(b"\r\n\r\n")).decode().split("\r\n")
        headers = {k.lower(): v for k, v in (h.split(": ", 1) for h in head[1:] if ": " in h)}
        seen.append({"path": head[0].split()[1], **headers})
        writer.write(routes.get(head[0].split()[1], reply("404 Not Found", b"")))
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    try:
        yield server.sockets[0].getsockname()[1], seen
    finally:
        server.close()
        await server.wait_closed()


def client(pol: OutboundPolicy, **kw: object) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=GuardedTransport(pol, **kw))  # type: ignore[arg-type]


async def test_a_request_goes_through_and_the_host_header_stays_the_real_name() -> None:
    calls: list[str] = []

    async def resolver(host: str, port: int) -> list[str]:
        calls.append(host)
        return ["127.0.0.1"]

    async with serve({"/hello": reply(body=b"hi")}) as (port, seen):
        async with client(policy(), resolver=resolver) as c:
            response = await c.get(f"http://llm.example.test:{port}/hello")

    assert response.status_code == 200 and response.content == b"hi"
    assert calls == ["llm.example.test"]
    assert seen[0]["host"] == f"llm.example.test:{port}"
    assert seen[0]["accept-encoding"] == "identity"


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://[fe80::1]/",
        "http://user:pw@example.com/",
        "http://2130706433/",
    ],
)
async def test_addresses_that_are_never_allowed_are_refused(url: str) -> None:
    async with client(policy()) as c:
        with pytest.raises(BlockedRequest):
            await c.get(url)


async def test_private_addresses_follow_the_policy() -> None:
    async with serve({"/": reply()}) as (port, _):
        async with client(policy(allow_private=True)) as c:
            assert (await c.get(f"http://127.0.0.1:{port}/")).status_code == 200
        async with client(policy(allow_private=False)) as c:
            with pytest.raises(BlockedRequest) as caught:
                await c.get(f"http://127.0.0.1:{port}/")
    assert caught.value.error.code in {"scheme_not_allowed", "blocked_destination"}


async def test_one_blocked_address_in_a_mixed_answer_refuses_the_request() -> None:
    async def resolver(host: str, port: int) -> list[str]:
        return ["93.184.216.34", "169.254.169.254"]

    async with client(policy(), resolver=resolver) as c:
        with pytest.raises(BlockedRequest) as caught:
            await c.get("http://mixed.example.test/")
    assert caught.value.error.code == "blocked_destination"


async def test_a_redirect_is_not_followed_by_the_guarded_client() -> None:
    routes = {"/go": reply("302 Found", b"", "Location: http://169.254.169.254/")}
    async with serve(routes) as (port, seen):
        async with guarded_client(policy()) as c:
            response = await c.get(f"http://127.0.0.1:{port}/go")
    assert response.status_code == 302 and len(seen) == 1


async def test_every_redirect_hop_is_checked_even_if_a_caller_follows_them() -> None:
    routes = {"/go": reply("302 Found", b"", "Location: http://169.254.169.254/latest/")}
    async with serve(routes) as (port, _):
        async with httpx.AsyncClient(
            transport=GuardedTransport(policy()), follow_redirects=True
        ) as c:
            with pytest.raises(BlockedRequest):
                await c.get(f"http://127.0.0.1:{port}/go")


async def test_a_response_over_the_cap_is_cut_off() -> None:
    async with serve({"/big": reply(body=b"x" * 5000)}) as (port, _):
        async with client(policy(max_bytes=100)) as c:
            with pytest.raises(BlockedRequest) as caught:
                await c.get(f"http://127.0.0.1:{port}/big")
    assert caught.value.error.code == "response_too_large"


async def test_an_encoded_response_is_refused_because_its_size_cannot_be_capped() -> None:
    routes = {"/z": reply("200 OK", b"zz", "Content-Encoding: gzip")}
    async with serve(routes) as (port, _):
        async with client(policy()) as c:
            with pytest.raises(BlockedRequest) as caught:
                await c.get(f"http://127.0.0.1:{port}/z")
    assert caught.value.error.code == "invalid_response"


async def test_an_error_does_not_say_what_lives_behind_the_address() -> None:
    async with client(policy()) as c:
        with pytest.raises(BlockedRequest) as caught:
            await c.get("http://169.254.169.254/")
    assert "169.254" not in str(caught.value)


async def test_a_host_header_set_by_a_caller_cannot_change_the_name_that_is_sent() -> None:
    async with serve({"/": reply()}) as (port, seen):
        async with client(policy()) as c:
            await c.get(f"http://127.0.0.1:{port}/", headers={"Host": "internal.example"})

    assert seen[0]["host"] == f"127.0.0.1:{port}"
