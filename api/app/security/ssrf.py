"""Outbound HTTP that cannot be pointed at addresses the operator did not allow."""

import asyncio
import ipaddress
import re
import socket
import ssl
from collections.abc import Awaitable, Callable, Mapping
from ipaddress import IPv4Address, IPv6Address

import httpx

from app.engine.base import FrozenBaseModel

Address = IPv4Address | IPv6Address
Resolver = Callable[[str, int], Awaitable[list[str]]]

HOST = re.compile(r"[A-Za-z0-9._:-]+")
# Decimal, hex, octal and short IPv4 spellings: the resolver would decode them, so refuse them.
NUMERIC_HOST = re.compile(r"(?:0[xX][0-9A-Fa-f]+|[0-9]+)(?:\.(?:0[xX][0-9A-Fa-f]+|[0-9]+))*")
# Headers that frame the message or the connection: the client sets them, a caller cannot.
FRAMING_HEADERS = frozenset(
    {
        "host",
        "content-length",
        "transfer-encoding",
        "connection",
        "keep-alive",
        "proxy-connection",
        "te",
        "trailer",
        "upgrade",
    }
)
# Says who is calling, so a site that sees abuse can find and report the server.
USER_AGENT = "decision-flow (+https://github.com/ShanuDey/decision-flow)"
NAT64 = ipaddress.ip_network("64:ff9b::/96")
# Cloud metadata services outside link-local: never a wanted target, even on a private network.
METADATA = tuple(
    ipaddress.ip_network(n)
    for n in ("100.100.100.200/32", "192.0.0.192/32", "fd00:ec2::254/128", "64:ff9b:1::/48")
)
SITE_LOCAL = ipaddress.ip_network("fec0::/10")
SIX_TO_FOUR = ipaddress.ip_network("2002::/16")


class OutboundError(Exception):
    """A refused or failed request. The message never says what lives behind an address."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class OutboundPolicy(FrozenBaseModel):
    allow_private: bool = True
    allowed_hosts: tuple[str, ...] = ()
    max_bytes: int
    timeout_seconds: float


class FetchResponse(FrozenBaseModel):
    status_code: int
    headers: tuple[tuple[str, str], ...]
    body: bytes


def _unwrap(ip: Address) -> Address:
    """The IPv4 address hidden inside a mapped, NAT64 or 6to4 IPv6 address, else the address."""
    for _ in range(2):
        if not isinstance(ip, IPv6Address):
            break
        if ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        elif ip in NAT64:
            ip = IPv4Address(ip.packed[-4:])
        elif ip in SIX_TO_FOUR:
            ip = IPv4Address(ip.packed[2:6])
    return ip


def is_blocked(ip: Address, allow_private: bool) -> bool:
    ip = _unwrap(ip)
    # Checked first: Python files ::1 under the reserved ::/8 range.
    if ip.is_loopback:
        return not allow_private
    # Link-local covers cloud metadata; none of these is ever a wanted target.
    if ip.is_link_local or ip.is_unspecified or ip.is_multicast or ip.is_reserved:
        return True
    if any(ip in network for network in METADATA):
        return True
    return not allow_private and (not ip.is_global or ip in SITE_LOCAL)


def host_allowed(host: str, allowed: tuple[str, ...]) -> bool:
    if not allowed:
        return True
    name = host.lower().rstrip(".")
    return any(
        name == rule or (rule.startswith("*.") and name.endswith(rule[1:])) for rule in allowed
    )


def _parse(raw: str, policy: OutboundPolicy) -> tuple[httpx.URL, str, int]:
    try:
        url = httpx.URL(raw)
    except httpx.InvalidURL:
        raise OutboundError("invalid_url", "The URL is not valid") from None
    if url.scheme not in ("http", "https"):
        raise OutboundError("scheme_not_allowed", "Only http and https URLs are allowed")
    if url.scheme != "https" and not policy.allow_private:
        raise OutboundError("scheme_not_allowed", "Only https URLs are allowed here")
    host = url.raw_host.decode("ascii", "replace")
    odd_ip = NUMERIC_HOST.fullmatch(host) and not _is_ip(host)
    if url.userinfo or not HOST.fullmatch(host) or odd_ip:
        raise OutboundError("invalid_url", "The URL is not valid")
    if not host_allowed(host, policy.allowed_hosts):
        shown = ", ".join(policy.allowed_hosts[:10])
        more = ", ..." if len(policy.allowed_hosts) > 10 else ""
        raise OutboundError(
            "host_not_allowed", f"This host is not on the allowed list ({shown}{more})"
        )
    port = url.port if url.port is not None else (443 if url.scheme == "https" else 80)
    if not 1 <= port <= 65535:
        raise OutboundError("invalid_url", "The URL is not valid")
    return url, host, port


TEMPLATE = re.compile(r"\{\{.*?\}\}")
WRITTEN_URL = re.compile(r"(https?)://([^/?#]*)", re.IGNORECASE)


def static_url_problem(raw: str, policy: OutboundPolicy) -> OutboundError | None:
    """Refusals knowable without a lookup, as in fetch; a templated host is only scheme-checked."""
    written = WRITTEN_URL.match(raw.strip())
    if written is None:
        return None
    if "{{" in written[2]:
        if written[1].lower() != "https" and not policy.allow_private:
            return OutboundError("scheme_not_allowed", "Only https URLs are allowed here")
        return None
    try:
        _, host, _ = _parse(TEMPLATE.sub("x", raw.strip()), policy)
    except OutboundError as error:
        return error
    if _is_ip(host):
        if is_blocked(ipaddress.ip_address(host), policy.allow_private):
            return OutboundError("blocked_destination", "This address is not allowed")
    elif not policy.allow_private and (host == "localhost" or host.endswith(".localhost")):
        return OutboundError("blocked_destination", "This address is not allowed")
    return None


async def system_resolver(host: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise OutboundError("dns_failed", "The host name could not be resolved") from None
    return list(dict.fromkeys(str(info[4][0]).split("%")[0] for info in infos))


async def _pick_address(host: str, port: int, policy: OutboundPolicy, resolve: Resolver) -> str:
    addresses = await resolve(host, port)
    if not addresses:
        raise OutboundError("dns_failed", "The host name could not be resolved")
    parsed = [ipaddress.ip_address(a) for a in addresses]
    # Every answer is checked: one bad address in a mixed reply refuses the request.
    if any(is_blocked(ip, policy.allow_private) for ip in parsed):
        raise OutboundError("blocked_destination", "This address is not allowed")
    return addresses[0]


def _request_headers(
    headers: Mapping[str, str] | None, host: str, url: httpx.URL
) -> dict[str, str]:
    sent = {k: v for k, v in (headers or {}).items() if k.lower() not in FRAMING_HEADERS}
    default = 443 if url.scheme == "https" else 80
    shown = f"[{host}]" if ":" in host else host
    if not any(k.lower() == "user-agent" for k in sent):
        sent["User-Agent"] = USER_AGENT
    sent["Host"] = shown if url.port in (None, default) else f"{shown}:{url.port}"
    return sent


async def _read_capped(response: httpx.Response, max_bytes: int) -> bytes:
    declared = response.headers.get("content-length", "")
    if (
        declared.isdigit()
        and int(declared) > max_bytes
        and "content-encoding" not in response.headers
    ):
        raise OutboundError("response_too_large", "The response is larger than the allowed size")
    body = bytearray()
    async for chunk in response.aiter_bytes():
        body += chunk
        if len(body) > max_bytes:
            raise OutboundError(
                "response_too_large", "The response is larger than the allowed size"
            )
    return bytes(body)


async def pin(
    policy: OutboundPolicy, url: str, resolver: Resolver = system_resolver
) -> tuple[httpx.URL, httpx.URL, str, dict[str, str]]:
    """Checks `url`, resolves it once, and returns (target, pinned, host, extensions)."""
    target, host, port = _parse(url, policy)
    address = await _pick_address(host, port, policy, resolver)
    pinned = target.copy_with(host=address, userinfo=b"", fragment=None)
    # The URL names the IP; Host and the TLS name stay the real host.
    literal = _is_ip(host)
    extensions = {} if literal or target.scheme != "https" else {"sni_hostname": host}
    return target, pinned, host, extensions


def _transport_error(exc: httpx.TransportError) -> OutboundError:
    if isinstance(exc, httpx.TimeoutException):
        return OutboundError("timeout", "The request timed out")
    if isinstance(exc, httpx.ProtocolError):
        return OutboundError(
            "invalid_request", "A header or the URL has characters that are not allowed"
        )
    if "CERTIFICATE_VERIFY_FAILED" in str(exc):
        return OutboundError("tls_failed", "The server's certificate could not be verified")
    return OutboundError("connect_failed", "Could not connect to the host")


async def fetch(
    policy: OutboundPolicy,
    method: str,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    content: bytes | None = None,
    resolver: Resolver = system_resolver,
    ssl_context: ssl.SSLContext | None = None,
) -> FetchResponse:
    """One request: the name is resolved once, every answer checked, and only that IP is used."""
    try:
        async with asyncio.timeout(policy.timeout_seconds):
            target, pinned, host, extensions = await pin(policy, url, resolver)
            async with httpx.AsyncClient(
                trust_env=False,
                follow_redirects=False,
                verify=ssl_context or True,
                timeout=policy.timeout_seconds,
            ) as client:
                request = client.build_request(
                    method,
                    pinned,
                    headers=_request_headers(headers, host, target),
                    content=content,
                    extensions=extensions,
                )
                response = await client.send(request, stream=True)
                try:
                    body = await _read_capped(response, policy.max_bytes)
                finally:
                    await response.aclose()
    except TimeoutError:
        raise OutboundError("timeout", "The request timed out") from None
    except OutboundError:
        raise
    except httpx.TransportError as exc:
        raise _transport_error(exc) from None
    except Exception:
        # The HTTP library can raise its own protocol errors on a bad header or body.
        raise OutboundError("invalid_request", "The request could not be sent") from None
    return FetchResponse(
        status_code=response.status_code,
        headers=tuple((k, v) for k, v in response.headers.multi_items()),
        body=body,
    )


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True
