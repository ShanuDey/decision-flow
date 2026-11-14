"""Rate limits, kept in memory (so per process), and the client IP they key on."""

import ipaddress
import math
import time
from collections import deque
from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.auth.deps import CurrentPrincipal
from app.auth.models import Principal
from app.engine.base import FrozenBaseModel
from app.errors import ApiError
from app.limits import Limits

WEB_PROVIDER = "web"
CLIENT_IP_HEADER = "x-client-ip"
FORWARDED_HEADER = "x-forwarded-for"
MAX_KEYS = 10_000
MINUTE, HOUR = 60, 3600
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
PUBLIC_PATHS = {"/health", "/ready", "/docs", "/redoc", "/openapi.json"}


class Decision(FrozenBaseModel):
    allowed: bool
    limit: int
    remaining: int
    reset: int  # seconds until a slot frees

    @property
    def headers(self) -> dict[str, str]:
        return {
            "RateLimit-Limit": str(self.limit),
            "RateLimit-Remaining": str(self.remaining),
            "RateLimit-Reset": str(self.reset),
        }


OFF = Decision(allowed=True, limit=0, remaining=0, reset=0)


class RateLimiter:
    """Sliding window per key. A limit of 0 turns it off."""

    def __init__(
        self,
        limit: int,
        window_seconds: int,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = MAX_KEYS,
    ) -> None:
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._max_keys = max_keys
        self._events: dict[str, deque[float]] = {}

    def _live(self, key: str, now: float) -> deque[float] | None:
        events = self._events.get(key)
        if events is None:
            return None
        while events and events[0] <= now - self.window:
            events.popleft()
        if not events:
            del self._events[key]
            return None
        return events

    def _decision(self, events: deque[float] | None, now: float, allowed: bool) -> Decision:
        used = len(events) if events else 0
        reset = math.ceil(events[0] + self.window - now) if events else self.window
        return Decision(
            allowed=allowed,
            limit=self.limit,
            remaining=max(self.limit - used, 0),
            reset=max(reset, 1),
        )

    def check(self, key: str) -> Decision:
        """Whether the key may act now, without counting an action."""
        if not self.limit:
            return OFF
        now = self._clock()
        events = self._live(key, now)
        return self._decision(events, now, allowed=(len(events) if events else 0) < self.limit)

    def hit(self, key: str) -> Decision:
        """Counts one action unless the key is already over its limit."""
        if not self.limit:
            return OFF
        now = self._clock()
        events = self._live(key, now)
        if events is not None and len(events) >= self.limit:
            return self._decision(events, now, allowed=False)
        if events is None:
            self._make_room(now)
            events = self._events[key] = deque()
        events.append(now)
        return self._decision(events, now, allowed=True)

    def _make_room(self, now: float) -> None:
        if len(self._events) < self._max_keys:
            return
        for key in list(self._events):
            self._live(key, now)
        while len(self._events) >= self._max_keys:
            del self._events[next(iter(self._events))]


class RateLimiters:
    """Every limiter, kept on `app.state` so tests can swap them."""

    def __init__(self, limits: Limits, trusted_proxy: int = 0) -> None:
        self.trusted_proxy = trusted_proxy
        self.notice = limits.notice_details()
        self.ip = RateLimiter(limits.rate_limit_ip_per_minute, MINUTE)
        self.ready = RateLimiter(limits.rate_limit_ready_per_minute, MINUTE)
        self.failed_auth = RateLimiter(limits.rate_limit_failed_auth_per_minute, MINUTE)
        self.user_writes = RateLimiter(limits.rate_limit_user_writes_per_minute, MINUTE)
        self.user_runs = RateLimiter(limits.rate_limit_user_runs_per_minute, MINUTE)
        self.new_workspaces = RateLimiter(limits.rate_limit_new_workspaces_per_ip_per_hour, HOUR)


def normalize_ip(value: str) -> str | None:
    """A canonical key for the address; IPv6 clients are grouped by /64."""
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped:
            return str(address.ipv4_mapped)
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def client_ip(peer: str | None, forwarded_for: str | None, trusted_proxy: int) -> str:
    """The connection IP, or with `trusted_proxy` hops the entry those proxies appended."""
    if trusted_proxy and forwarded_for:
        parts = [p for p in forwarded_for.split(",") if p.strip()]
        if len(parts) >= trusted_proxy:
            found = normalize_ip(parts[-trusted_proxy])
            if found:
                return found
    return normalize_ip(peer or "") or "unknown"


def visitor_ip(principal: Principal, request: Request) -> str:
    """The visitor behind the web app, which the web app vouches for with its own token."""
    if principal.provider == WEB_PROVIDER:
        forwarded = normalize_ip(request.headers.get(CLIENT_IP_HEADER, ""))
        if forwarded:
            return forwarded
    limiters: RateLimiters = request.app.state.rate_limiters
    peer = request.client.host if request.client else None
    return client_ip(peer, request.headers.get(FORWARDED_HEADER), limiters.trusted_proxy)


def refusal(decision: Decision, scope: str, notice: dict[str, str]) -> ApiError:
    unit = "second" if decision.reset == 1 else "seconds"
    what = "failed sign-in attempts from this address" if scope == "failed_auth" else "requests"
    return ApiError(
        429,
        "rate_limited",
        f"Too many {what}; try again in {decision.reset} {unit}",
        {"scope": scope, "limit": decision.limit, "retry_after": decision.reset, **notice},
        {"Retry-After": str(decision.reset), **decision.headers},
    )


class RateLimitMiddleware:
    """Per connection IP before authentication; failed sign-ins are counted.

    A signed-in request comes from the web app's own servers, shared by every visitor, so it is
    charged per visitor after authentication instead (`limit_visitor`).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limiters: RateLimiters = scope["app"].state.rate_limiters
        peer = scope["client"][0] if scope.get("client") else None
        ip = client_ip(peer, Headers(scope=scope).get(FORWARDED_HEADER), limiters.trusted_proxy)

        blocked = limiters.failed_auth.check(ip)
        if not blocked.allowed:
            await self._refuse(blocked, "failed_auth", limiters, scope, receive, send)
            return
        path = scope["path"]
        signed_in = Headers(scope=scope).get("authorization", "").lower().startswith("bearer ")
        decision = None
        if path == "/ready":
            decision = limiters.ready.hit(ip)
        elif not signed_in or path in PUBLIC_PATHS:
            decision = limiters.ip.hit(ip)
        if decision is not None and not decision.allowed:
            name = "ready" if path == "/ready" else "ip"
            await self._refuse(decision, name, limiters, scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                if message["status"] in (401, 403):
                    limiters.failed_auth.hit(ip)
                if decision is not None and decision.limit:
                    headers = MutableHeaders(scope=message)
                    for name_, value in decision.headers.items():
                        if name_ not in headers:
                            headers[name_] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)

    @staticmethod
    async def _refuse(
        decision: Decision,
        name: str,
        limiters: RateLimiters,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        error = refusal(decision, name, limiters.notice)
        response = JSONResponse(error.body.model_dump(), status_code=429, headers=error.headers)
        await response(scope, receive, send)


def _charge(request: Request, response: Response, name: str, key: str, scope: str) -> None:
    limiters: RateLimiters = request.app.state.rate_limiters
    decision = getattr(limiters, name).hit(key)
    if not decision.allowed:
        raise refusal(decision, scope, limiters.notice)
    if decision.limit:
        response.headers.update(decision.headers)


def _user_key(principal: Principal) -> str:
    return f"{principal.provider}:{principal.sub}"


async def limit_visitor(request: Request, response: Response, principal: CurrentPrincipal) -> None:
    _charge(request, response, "ip", visitor_ip(principal, request), "ip")


async def limit_writes(request: Request, response: Response, principal: CurrentPrincipal) -> None:
    if request.method not in SAFE_METHODS:
        _charge(request, response, "user_writes", _user_key(principal), "user")


async def limit_runs(request: Request, response: Response, principal: CurrentPrincipal) -> None:
    _charge(request, response, "user_runs", _user_key(principal), "runs")


def check_new_workspace(principal: Principal, request: Request) -> None:
    """Refuses before anything is created; the account is charged once it exists."""
    limiters: RateLimiters = request.app.state.rate_limiters
    decision = limiters.new_workspaces.check(visitor_ip(principal, request))
    if not decision.allowed:
        raise refusal(decision, "new_workspaces", limiters.notice)


def charge_new_workspace(principal: Principal, request: Request) -> None:
    limiters: RateLimiters = request.app.state.rate_limiters
    limiters.new_workspaces.hit(visitor_ip(principal, request))
