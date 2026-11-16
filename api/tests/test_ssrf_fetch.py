import asyncio
import datetime
import socket
import ssl
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.security.ssrf import OutboundError, OutboundPolicy, fetch

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class Seen:
    def __init__(self) -> None:
        self.connections = 0
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.sni: list[str | None] = []


class Resolver:
    """Answers in order, repeating the last; remembers every question."""

    def __init__(self, *answers: list[str]) -> None:
        self.answers = answers
        self.asked: list[tuple[str, int]] = []

    async def __call__(self, host: str, port: int) -> list[str]:
        self.asked.append((host, port))
        return self.answers[min(len(self.asked), len(self.answers)) - 1]


def policy(**overrides: object) -> OutboundPolicy:
    values = {"allow_private": True, "max_bytes": 1000, "timeout_seconds": 5, **overrides}
    return OutboundPolicy(**values)  # type: ignore[arg-type]


async def respond(writer: asyncio.StreamWriter, status: str, headers: str, body: bytes) -> None:
    writer.write(f"HTTP/1.1 {status}\r\n{headers}Connection: close\r\n\r\n".encode() + body)
    await writer.drain()


@asynccontextmanager
async def serve(context: ssl.SSLContext | None = None) -> AsyncIterator[tuple[int, Seen]]:
    seen = Seen()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        seen.connections += 1
        try:
            head = await reader.readuntil(b"\r\n\r\n")
        except (asyncio.IncompleteReadError, ConnectionError):
            writer.close()
            return
        lines = head.decode().split("\r\n")
        path = lines[0].split()[1]
        headers = {
            k.lower(): v for k, v in (line.split(": ", 1) for line in lines[1:] if ": " in line)
        }
        seen.requests.append((path, headers))
        if path == "/redir":
            await respond(writer, "302 Found", f"Location: {headers['host']}/second\r\n", b"")
        elif path == "/big-length":
            await respond(writer, "200 OK", "Content-Length: 5000\r\n", b"x" * 5000)
        elif path == "/big-stream":
            await respond(writer, "200 OK", "", b"x" * 5000)
        elif path == "/slow":
            await asyncio.sleep(2)
            await respond(writer, "200 OK", "Content-Length: 2\r\n", b"ok")
        else:
            await respond(writer, "200 OK", "Content-Length: 2\r\n", b"ok")
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0, ssl=context)
    try:
        yield server.sockets[0].getsockname()[1], seen
    finally:
        server.close()
        await server.wait_closed()


def make_certificate(directory: Path, name: str) -> tuple[Path, Path]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(name)]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = directory / f"{name}.crt", directory / f"{name}.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


def tls_server_context(cert: Path, key: Path, seen: Seen) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    context.sni_callback = lambda _sock, name, _ctx: seen.sni.append(name)
    return context


async def refused(coro: object) -> OutboundError:
    with pytest.raises(OutboundError) as error:
        await coro  # type: ignore[misc]
    return error.value


async def test_a_local_server_is_reachable_when_private_networks_are_allowed() -> None:
    async with serve() as (port, seen):
        response = await fetch(policy(), "GET", f"http://127.0.0.1:{port}/hello")

    assert (response.status_code, response.body) == (200, b"ok")
    assert seen.connections == 1


async def test_with_the_flag_off_a_local_server_is_never_contacted() -> None:
    async with serve() as (port, seen):
        https = await refused(
            fetch(policy(allow_private=False), "GET", f"https://127.0.0.1:{port}/")
        )
        http = await refused(fetch(policy(allow_private=False), "GET", f"http://127.0.0.1:{port}/"))

    assert https.code == "blocked_destination" and http.code == "scheme_not_allowed"
    assert seen.connections == 0


@pytest.mark.parametrize("allow_private", [True, False])
async def test_metadata_and_unspecified_addresses_are_refused_even_when_private_is_allowed(
    allow_private: bool,
) -> None:
    async with serve() as (port, seen):
        for url in (
            "https://169.254.169.254/latest/meta-data/",
            f"https://0.0.0.0:{port}/",
            f"https://[::ffff:169.254.169.254]:{port}/",
        ):
            error = await refused(fetch(policy(allow_private=allow_private), "GET", url))
            assert error.code == "blocked_destination", url

    assert seen.connections == 0


@pytest.mark.parametrize("spelling", ["127.1", "2130706433", "0x7f000001", "017700000001"])
async def test_odd_spellings_of_loopback_never_reach_the_server(spelling: str) -> None:
    async with serve() as (port, seen):
        error = await refused(
            fetch(
                policy(allow_private=True),
                "GET",
                f"https://{spelling}:{port}/",
            )
        )

    assert error.code == "invalid_url"
    assert seen.connections == 0


async def test_a_name_that_resolves_to_an_internal_address_is_refused() -> None:
    for answer in ("10.0.0.5", "127.0.0.1", "192.168.0.10", "::1"):
        resolver = Resolver([answer])
        error = await refused(
            fetch(
                policy(allow_private=False), "GET", "https://internal.example/", resolver=resolver
            )
        )
        assert error.code == "blocked_destination", answer


async def test_a_name_that_resolves_to_metadata_is_refused_even_when_private_is_allowed() -> None:
    error = await refused(
        fetch(
            policy(),
            "GET",
            "http://metadata.example/latest/meta-data/",
            resolver=Resolver(["169.254.169.254"]),
        )
    )

    assert error.code == "blocked_destination"


@pytest.mark.parametrize("answers", [["8.8.8.8", "127.0.0.1"], ["127.0.0.1", "8.8.8.8"]])
async def test_one_bad_address_in_a_mixed_answer_refuses_the_request(answers: list[str]) -> None:
    error = await refused(
        fetch(
            policy(allow_private=False),
            "GET",
            "https://mixed.example/",
            resolver=Resolver(answers),
        )
    )

    assert error.code == "blocked_destination"


async def test_the_name_is_resolved_once_and_the_connection_goes_to_that_answer() -> None:
    resolver = Resolver(["127.0.0.1"], ["10.0.0.1"])
    async with serve() as (port, seen):
        response = await fetch(
            policy(),
            "GET",
            f"http://api.example.test:{port}/x",
            headers={"Host": "evil.example", "X-Trace": "1"},
            resolver=resolver,
        )

    assert response.status_code == 200
    assert resolver.asked == [("api.example.test", port)]
    ((_, headers),) = seen.requests
    assert headers["host"] == f"api.example.test:{port}"
    assert headers["x-trace"] == "1"


async def test_a_redirect_comes_back_as_data_and_is_not_followed() -> None:
    async with serve() as (port, seen):
        response = await fetch(policy(), "GET", f"http://127.0.0.1:{port}/redir")

    assert response.status_code == 302
    assert dict(response.headers)["location"] == f"127.0.0.1:{port}/second"
    assert [path for path, _ in seen.requests] == ["/redir"]


@pytest.mark.parametrize("path", ["/big-length", "/big-stream"])
async def test_a_response_over_the_cap_is_cut_off(path: str) -> None:
    async with serve() as (port, _):
        error = await refused(
            fetch(policy(max_bytes=1000), "GET", f"http://127.0.0.1:{port}{path}")
        )

    assert error.code == "response_too_large"


async def test_a_slow_response_times_out() -> None:
    async with serve() as (port, _):
        error = await refused(
            fetch(policy(timeout_seconds=0.3), "GET", f"http://127.0.0.1:{port}/slow")
        )

    assert error.code == "timeout"


async def test_a_closed_port_is_a_connect_failure_that_names_no_address() -> None:
    with socket.socket() as free:
        free.bind(("127.0.0.1", 0))
        port = free.getsockname()[1]

    error = await refused(fetch(policy(), "GET", f"http://127.0.0.1:{port}/"))

    assert error.code == "connect_failed"
    assert "127.0.0.1" not in error.message


async def test_proxy_settings_in_the_environment_are_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("HTTP_PROXY", "ALL_PROXY", "http_proxy", "all_proxy"):
        monkeypatch.setenv(name, "http://127.0.0.1:1")
    async with serve() as (port, seen):
        response = await fetch(policy(), "GET", f"http://127.0.0.1:{port}/")

    assert response.status_code == 200 and seen.connections == 1


async def test_https_checks_the_certificate_against_the_name_not_the_pinned_ip(
    tmp_path: Path,
) -> None:
    cert, key = make_certificate(tmp_path, "api.example.test")
    seen_tls = Seen()
    client = ssl.create_default_context(cafile=cert)
    async with serve(tls_server_context(cert, key, seen_tls)) as (port, seen):
        seen.sni = seen_tls.sni
        response = await fetch(
            policy(),
            "GET",
            f"https://api.example.test:{port}/",
            resolver=Resolver(["127.0.0.1"]),
            ssl_context=client,
        )

    assert (response.status_code, response.body) == (200, b"ok")
    assert seen_tls.sni == ["api.example.test"]
    assert seen.requests[0][1]["host"] == f"api.example.test:{port}"


async def test_a_certificate_for_another_name_is_refused(tmp_path: Path) -> None:
    cert, key = make_certificate(tmp_path, "other.example.test")
    client = ssl.create_default_context(cafile=cert)
    async with serve(tls_server_context(cert, key, Seen())) as (port, _):
        error = await refused(
            fetch(
                policy(),
                "GET",
                f"https://api.example.test:{port}/",
                resolver=Resolver(["127.0.0.1"]),
                ssl_context=client,
            )
        )

    assert error.code == "tls_failed"


@pytest.mark.parametrize(
    "headers",
    [
        {"X-A": "a\r\nX-Injected: 1"},
        {"X-A": "a\nX-Injected: 1"},
        {"X-A\r\nX-Injected": "1"},
        {"X-A": "a\x00b"},
    ],
)
async def test_a_header_with_a_line_break_or_null_is_refused_before_anything_is_sent(
    headers: dict[str, str],
) -> None:
    async with serve() as (port, seen):
        error = await refused(fetch(policy(), "GET", f"http://127.0.0.1:{port}/", headers=headers))

    assert error.code == "invalid_request"
    assert seen.requests == []


@pytest.mark.parametrize("target", ["/a\r\nX-Injected: 1", "/p?x=a\r\nb"])
async def test_a_url_with_a_line_break_is_refused(target: str) -> None:
    async with serve() as (port, seen):
        error = await refused(fetch(policy(), "GET", f"http://127.0.0.1:{port}{target}"))

    assert error.code == "invalid_url" and seen.requests == []


async def test_an_encoded_line_break_stays_encoded_and_a_space_is_encoded() -> None:
    async with serve() as (port, seen):
        await fetch(policy(), "GET", f"http://127.0.0.1:{port}/a%0d%0aX-Injected:1")
        await fetch(policy(), "GET", f"http://127.0.0.1:{port}/a b")

    paths = [path for path, _ in seen.requests]
    assert paths == ["/a%0d%0aX-Injected:1", "/a%20b"]
    assert all("x-injected" not in headers for _, headers in seen.requests)


async def test_headers_that_frame_the_message_are_the_clients_to_set() -> None:
    async with serve() as (port, seen):
        response = await fetch(
            policy(),
            "POST",
            f"http://127.0.0.1:{port}/",
            headers={
                "Content-Length": "999",
                "Transfer-Encoding": "chunked",
                "Connection": "Upgrade",
                "Upgrade": "websocket",
                "TE": "trailers",
                "X-Kept": "1",
            },
            content=b"abc",
        )

    assert response.status_code == 200
    ((_, headers),) = seen.requests
    assert headers["content-length"] == "3"
    assert headers["x-kept"] == "1"
    for name in ("transfer-encoding", "upgrade", "te"):
        assert name not in headers
    assert headers.get("connection", "keep-alive") != "Upgrade"


async def test_the_request_says_who_is_calling_unless_the_caller_says_otherwise() -> None:
    async with serve() as (port, seen):
        await fetch(policy(), "GET", f"http://127.0.0.1:{port}/")
        await fetch(policy(), "GET", f"http://127.0.0.1:{port}/", headers={"user-agent": "mine"})

    first, second = (headers for _, headers in seen.requests)
    assert first["user-agent"].startswith("decision-flow")
    assert second["user-agent"] == "mine"
