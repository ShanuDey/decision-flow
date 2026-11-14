import httpx
import pytest

from app.auth.models import Principal
from app.limits import Limits
from app.main import app
from app.ratelimit import (
    RateLimiter,
    RateLimiters,
    client_ip,
    normalize_ip,
    visitor_ip,
)
from tests.auth_helpers import bearer
from tests.conftest import FakeWorkspaceStore, create_flow

pytestmark = pytest.mark.anyio


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def limiters(trusted_proxy: int = 0, **fields: int | str) -> None:
    """Replace the app's limiters; every limit not named here stays off."""
    off = {name: 0 for name in Limits.model_fields if name.startswith("rate_limit_")}
    app.state.rate_limiters = RateLimiters(
        Limits(_env_file=None, **{**off, **fields}), trusted_proxy
    )


def test_a_limiter_refuses_after_the_limit_and_recovers_with_the_window() -> None:
    clock = Clock()
    limiter = RateLimiter(2, 60, clock)
    assert limiter.hit("a").remaining == 1
    assert limiter.hit("a").remaining == 0
    refused = limiter.hit("a")
    assert (refused.allowed, refused.reset) == (False, 60)
    assert limiter.hit("b").allowed

    clock.now += 30
    assert limiter.hit("a").reset == 30
    clock.now += 31
    assert limiter.hit("a").allowed


def test_check_does_not_count() -> None:
    limiter = RateLimiter(1, 60, Clock())
    assert limiter.check("a").allowed and limiter.check("a").allowed
    limiter.hit("a")
    assert not limiter.check("a").allowed


def test_zero_turns_a_limiter_off() -> None:
    limiter = RateLimiter(0, 60, Clock())
    assert all(limiter.hit("a").allowed for _ in range(1000))
    assert limiter.hit("a").limit == 0


def test_memory_is_bounded_by_dropping_the_oldest_keys() -> None:
    limiter = RateLimiter(1, 60, Clock(), max_keys=3)
    for key in "abcd":
        limiter.hit(key)
    assert len(limiter._events) == 3
    assert limiter.hit("a").allowed  # evicted, so counted as new


def test_a_spoofed_forwarded_header_is_ignored_without_a_trusted_proxy() -> None:
    assert client_ip("9.9.9.9", "1.2.3.4", 0) == "9.9.9.9"


def test_trusted_proxies_pick_the_entry_they_appended_not_the_one_the_client_sent() -> None:
    header = "6.6.6.6, 1.2.3.4, 10.0.0.1"
    assert client_ip("9.9.9.9", header, 1) == "10.0.0.1"
    assert client_ip("9.9.9.9", header, 2) == "1.2.3.4"
    assert client_ip("9.9.9.9", "1.2.3.4", 2) == "9.9.9.9"
    assert client_ip("9.9.9.9", "not-an-ip", 1) == "9.9.9.9"
    assert client_ip(None, None, 0) == "unknown"


def test_ipv6_clients_share_a_bucket_per_64() -> None:
    assert normalize_ip("2001:db8::1") == normalize_ip("2001:db8::ffff") == "2001:db8::/64"
    assert normalize_ip("::ffff:1.2.3.4") == "1.2.3.4"
    assert normalize_ip("junk") is None


async def test_the_ip_limit_refuses_with_headers_and_the_notice(
    anon_client: httpx.AsyncClient,
) -> None:
    limiters(rate_limit_ip_per_minute=2, limit_notice="Free demo.")
    first = await anon_client.get("/health")
    assert first.headers["ratelimit-limit"] == "2"
    assert first.headers["ratelimit-remaining"] == "1"
    await anon_client.get("/health")

    refused = await anon_client.get("/health")
    assert refused.status_code == 429
    assert refused.headers["retry-after"] == refused.headers["ratelimit-reset"]
    body = refused.json()
    assert body["code"] == "rate_limited"
    assert body["details"]["scope"] == "ip"
    assert body["details"]["notice"] == "Free demo."


async def test_ready_has_its_own_stricter_limit(anon_client: httpx.AsyncClient) -> None:
    limiters(rate_limit_ip_per_minute=100, rate_limit_ready_per_minute=1)
    await anon_client.get("/ready")
    refused = await anon_client.get("/ready")
    assert refused.status_code == 429
    assert refused.json()["details"]["scope"] == "ready"
    assert (await anon_client.get("/health")).status_code == 200


async def test_failed_sign_ins_block_that_ip_but_not_another(
    anon_client: httpx.AsyncClient,
) -> None:
    limiters(trusted_proxy=1, rate_limit_failed_auth_per_minute=2)
    bad = {"Authorization": "Bearer nope"}
    for _ in range(2):
        r = await anon_client.get("/flows", headers={**bad, "X-Forwarded-For": "1.1.1.1"})
        assert r.status_code == 401

    blocked = await anon_client.get("/health", headers={"X-Forwarded-For": "1.1.1.1"})
    assert blocked.status_code == 429
    assert blocked.json()["details"]["scope"] == "failed_auth"
    other = await anon_client.get("/health", headers={"X-Forwarded-For": "2.2.2.2"})
    assert other.status_code == 200


async def test_a_forged_forwarded_header_cannot_dodge_the_limit_without_a_trusted_proxy(
    anon_client: httpx.AsyncClient,
) -> None:
    limiters(rate_limit_ip_per_minute=1)
    await anon_client.get("/health", headers={"X-Forwarded-For": "1.1.1.1"})
    refused = await anon_client.get("/health", headers={"X-Forwarded-For": "2.2.2.2"})
    assert refused.status_code == 429


async def test_a_refusal_still_carries_cors_headers(anon_client: httpx.AsyncClient) -> None:
    limiters(rate_limit_ip_per_minute=1)
    origin = {"Origin": "http://localhost:3000"}
    await anon_client.get("/health", headers=origin)
    refused = await anon_client.get("/health", headers=origin)
    assert refused.status_code == 429
    assert refused.headers["access-control-allow-origin"] == "http://localhost:3000"


async def test_user_write_limits_are_per_user_and_ignore_reads(
    client: httpx.AsyncClient,
) -> None:
    limiters(rate_limit_user_writes_per_minute=2)
    for _ in range(5):
        assert (await client.get("/flows")).status_code == 200
    await create_flow(client)
    await create_flow(client)

    refused = await client.post("/flows", json={"name": "Third"})
    assert refused.status_code == 429
    assert refused.json()["details"]["scope"] == "user"
    assert refused.headers["retry-after"]

    other = await client.post("/flows", json={"name": "Mine"}, headers=bearer(sub="user-2"))
    assert other.status_code == 201


async def test_runs_have_a_tighter_limit_than_other_writes(client: httpx.AsyncClient) -> None:
    limiters(rate_limit_user_writes_per_minute=50, rate_limit_user_runs_per_minute=1)
    flow = await create_flow(client)
    run = {"test": True, "input": {}}
    assert (await client.post(f"/flows/{flow['id']}/runs", json=run)).status_code == 200

    refused = await client.post(f"/flows/{flow['id']}/runs", json=run)
    assert refused.status_code == 429
    assert refused.json()["details"]["scope"] == "runs"


async def test_new_workspaces_are_capped_per_visitor_ip(
    client: httpx.AsyncClient, workspace_store: FakeWorkspaceStore
) -> None:
    limiters(rate_limit_new_workspaces_per_ip_per_hour=2)
    visitor = {"X-Client-IP": "7.7.7.7"}
    for sub in ("a", "b"):
        response = await client.get("/flows", headers={**bearer(sub=sub), **visitor})
        assert response.status_code == 200

    refused = await client.get("/flows", headers={**bearer(sub="c"), **visitor})
    assert refused.status_code == 429
    assert refused.json()["details"]["scope"] == "new_workspaces"
    assert ("web", "c") not in workspace_store.members

    again = await client.get("/flows", headers={**bearer(sub="a"), **visitor})
    assert again.status_code == 200
    elsewhere = await client.get("/flows", headers={**bearer(sub="d"), "X-Client-IP": "8.8.8.8"})
    assert elsewhere.status_code == 200


def test_the_web_apps_visitor_ip_is_trusted_only_for_its_own_provider() -> None:
    limiters(trusted_proxy=0)
    request = httpx.Request("GET", "http://t", headers={"X-Client-IP": "7.7.7.7"})

    class Fake:
        headers = request.headers
        client = type("C", (), {"host": "9.9.9.9"})()
        app = app

    web = Principal(sub="s", provider="web", email=None, name=None)
    github = Principal(sub="s", provider="github", email=None, name=None)
    assert visitor_ip(web, Fake()) == "7.7.7.7"  # type: ignore[arg-type]
    assert visitor_ip(github, Fake()) == "9.9.9.9"  # type: ignore[arg-type]


async def test_signed_in_visitors_behind_one_web_server_do_not_share_a_limit(
    client: httpx.AsyncClient,
) -> None:
    limiters(rate_limit_ip_per_minute=2)
    for visitor in ("1.1.1.1", "2.2.2.2", "3.3.3.3"):
        for _ in range(2):
            response = await client.get("/flows", headers={"X-Client-IP": visitor})
            assert response.status_code == 200

    refused = await client.get("/flows", headers={"X-Client-IP": "1.1.1.1"})
    assert refused.status_code == 429
    assert refused.json()["details"]["scope"] == "ip"


async def test_a_bearer_header_does_not_dodge_the_public_route_limits(
    anon_client: httpx.AsyncClient,
) -> None:
    limiters(rate_limit_ip_per_minute=1, rate_limit_ready_per_minute=1)
    bogus = {"Authorization": "Bearer junk"}
    for path in ("/health", "/ready"):
        await anon_client.get(path, headers=bogus)
        assert (await anon_client.get(path, headers=bogus)).status_code == 429


async def test_headers_on_signed_in_routes_come_from_the_visitor_limit(
    client: httpx.AsyncClient,
) -> None:
    limiters(rate_limit_ip_per_minute=5)
    response = await client.get("/flows", headers={"X-Client-IP": "1.1.1.1"})
    assert response.headers["ratelimit-limit"] == "5"
    assert response.headers["ratelimit-remaining"] == "4"


async def test_a_lost_first_sign_in_race_is_not_charged_twice(
    client: httpx.AsyncClient, workspace_store: FakeWorkspaceStore
) -> None:
    limiters(rate_limit_new_workspaces_per_ip_per_hour=2)
    visitor = {"X-Client-IP": "7.7.7.7"}
    for _ in range(3):
        response = await client.get("/flows", headers={**bearer(sub="a"), **visitor})
        assert response.status_code == 200
    assert (await client.get("/flows", headers={**bearer(sub="b"), **visitor})).status_code == 200
    assert (await client.get("/flows", headers={**bearer(sub="c"), **visitor})).status_code == 429


def test_the_refusal_message_is_singular_for_one_second_and_names_failed_sign_ins() -> None:
    from app.ratelimit import Decision, refusal

    one = Decision(allowed=False, limit=1, remaining=0, reset=1)
    assert refusal(one, "ip", {}).body.message.endswith("in 1 second")
    assert "failed sign-in" in refusal(one, "failed_auth", {}).body.message
