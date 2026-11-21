"""An httpx transport that applies the outbound policy to every request an SDK makes."""

import ssl
from collections.abc import AsyncIterator
from functools import lru_cache

import httpx

from app.security.ssrf import OutboundError, OutboundPolicy, Resolver, pin, system_resolver


@lru_cache(maxsize=1)
def shared_ssl_context() -> ssl.SSLContext:
    """Built once: creating a context loads the CA bundle, which is slow to repeat per request."""
    return httpx.create_ssl_context()


class BlockedRequest(httpx.ConnectError):
    """A request the policy refused or cut off; `error` never names what lives behind an address."""

    def __init__(self, error: OutboundError, request: httpx.Request | None = None) -> None:
        super().__init__(error.message, request=request)
        self.error = error


class _Capped(httpx.AsyncByteStream):
    def __init__(self, inner: httpx.AsyncByteStream, limit: int, request: httpx.Request) -> None:
        self._inner = inner
        self._limit = limit
        self._request = request

    async def __aiter__(self) -> AsyncIterator[bytes]:
        total = 0
        async for chunk in self._inner:
            total += len(chunk)
            if total > self._limit:
                error = OutboundError(
                    "response_too_large", "The response is larger than the allowed size"
                )
                raise BlockedRequest(error, self._request)
            yield chunk

    async def aclose(self) -> None:
        await self._inner.aclose()


class GuardedTransport(httpx.AsyncBaseTransport):
    """Each request, including any redirect hop, is checked, resolved once and sent to that IP."""

    def __init__(
        self,
        policy: OutboundPolicy,
        resolver: Resolver = system_resolver,
        ssl_context: ssl.SSLContext | None = None,
        drop_headers: tuple[str, ...] = (),
    ) -> None:
        self._drop = frozenset(name.lower() for name in drop_headers)
        self._policy = policy
        self._resolver = resolver
        self._inner = httpx.AsyncHTTPTransport(
            verify=ssl_context or shared_ssl_context(), trust_env=False
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        try:
            _, pinned, _, extensions = await pin(self._policy, str(request.url), self._resolver)
        except OutboundError as exc:
            raise BlockedRequest(exc, request) from None
        headers = httpx.Headers(request.headers)
        for name in self._drop:
            headers.pop(name, None)
        # The name that was checked is the name sent, whatever a caller put in a header.
        headers["Host"] = request.url.netloc.decode("ascii")
        # The cap counts bytes as sent, so an encoded body could expand past it.
        headers["Accept-Encoding"] = "identity"
        outgoing = httpx.Request(
            request.method,
            pinned,
            headers=headers,
            stream=request.stream,
            extensions={**request.extensions, **extensions},
        )
        response = await self._inner.handle_async_request(outgoing)
        if response.headers.get("content-encoding", "identity").lower() != "identity":
            await response.aclose()
            error = OutboundError("invalid_response", "The response uses an unsupported encoding")
            raise BlockedRequest(error, request)
        if not isinstance(response.stream, httpx.AsyncByteStream):
            await response.aclose()
            error = OutboundError("invalid_response", "The response could not be read")
            raise BlockedRequest(error, request)
        return httpx.Response(
            response.status_code,
            headers=response.headers,
            stream=_Capped(response.stream, self._policy.max_bytes, request),
            extensions=response.extensions,
        )

    async def aclose(self) -> None:
        await self._inner.aclose()


def guarded_client(
    policy: OutboundPolicy,
    resolver: Resolver = system_resolver,
    ssl_context: ssl.SSLContext | None = None,
    drop_headers: tuple[str, ...] = (),
) -> httpx.AsyncClient:
    """The one client SDKs should be given; it never follows a redirect without re-checking it."""
    return httpx.AsyncClient(
        transport=GuardedTransport(policy, resolver, ssl_context, drop_headers),
        follow_redirects=False,
        trust_env=False,
        timeout=policy.timeout_seconds,
    )
