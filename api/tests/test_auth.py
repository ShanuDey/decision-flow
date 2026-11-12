import asyncio
import json
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import ValidationError

from app import main
from app.auth import verifiers
from app.auth.config import JwtProvider, UserinfoProvider
from app.auth.service import Authenticator, build_authenticator
from app.auth.verifiers import (
    JWKS_TTL_SECONDS,
    InvalidToken,
    JwtVerifier,
    ProviderUnavailable,
    UserinfoVerifier,
)
from app.errors import ApiError
from app.settings import Settings
from tests.auth_helpers import (
    AUDIENCE,
    ISSUER,
    PROVIDER_CONFIG,
    PUBLIC_PEM,
    bearer,
    mint,
)


def other_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


@pytest.mark.anyio
async def test_health_needs_no_token(anon_client: httpx.AsyncClient) -> None:
    assert (await anon_client.get("/health")).status_code == 200


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/flows", "/runs", "/me"])
async def test_protected_routes_reject_a_missing_token(
    anon_client: httpx.AsyncClient, path: str
) -> None:
    response = await anon_client.get(path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["code"] == "unauthenticated"


@pytest.mark.anyio
async def test_me_returns_the_principal(anon_client: httpx.AsyncClient) -> None:
    headers = bearer(email="a@acme.com", name="Alex")
    response = await anon_client.get("/me", headers=headers)
    assert response.status_code == 200
    assert response.json() == {
        "sub": "user-1",
        "provider": "web",
        "email": "a@acme.com",
        "name": "Alex",
    }


@pytest.mark.anyio
async def test_a_valid_token_reaches_the_flows(client: httpx.AsyncClient) -> None:
    assert (await client.get("/flows")).status_code == 200


@pytest.mark.anyio
@pytest.mark.parametrize(
    "token",
    [
        mint(issuer="https://evil.test"),
        mint(audience="someone-else"),
        mint(expires_in=-10),
        mint(key=other_pem()),
        "not-a-token",
        "a.b.c",
    ],
    ids=["issuer", "audience", "expired", "signature", "garbage", "malformed"],
)
async def test_bad_tokens_are_rejected(anon_client: httpx.AsyncClient, token: str) -> None:
    response = await anon_client.get("/me", headers=bearer(token))
    assert response.status_code == 401


@pytest.mark.anyio
async def test_a_token_signed_with_a_symmetric_algorithm_is_rejected(
    anon_client: httpx.AsyncClient,
) -> None:
    token = jwt.encode(
        {"sub": "x", "iss": ISSUER, "aud": AUDIENCE, "exp": 4102444800},
        "secret-secret-secret-secret-secret-secret",
        algorithm="HS256",
    )
    assert (await anon_client.get("/me", headers=bearer(token))).status_code == 401


@pytest.mark.anyio
async def test_an_unsigned_token_is_rejected(anon_client: httpx.AsyncClient) -> None:
    token = jwt.encode(
        {"sub": "x", "iss": ISSUER, "aud": AUDIENCE, "exp": 4102444800}, None, algorithm="none"
    )
    assert (await anon_client.get("/me", headers=bearer(token))).status_code == 401


@pytest.mark.anyio
async def test_the_authorization_header_is_allowed_by_cors(
    anon_client: httpx.AsyncClient,
) -> None:
    response = await anon_client.options(
        "/flows",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def jwt_provider(**overrides: Any) -> JwtProvider:
    return JwtProvider.model_validate({**PROVIDER_CONFIG, **overrides})


def authenticator(*providers: Any, domains: list[str] | None = None) -> Authenticator:
    return Authenticator(list(providers), domains or [], httpx.AsyncClient())


@pytest.mark.anyio
async def test_the_domain_allow_list_requires_a_verified_email() -> None:
    auth = authenticator(jwt_provider(), domains=["acme.com"])
    ok = await auth.authenticate(mint(email="a@Acme.com", email_verified=True))
    assert ok.email == "a@Acme.com"
    for claims in (
        {"email": "a@acme.com"},
        {"email": "a@acme.com", "email_verified": False},
        {"email": "a@other.com", "email_verified": True},
        {},
    ):
        with pytest.raises(ApiError) as caught:
            await auth.authenticate(mint(**claims))
        assert caught.value.status == 403


@pytest.mark.anyio
async def test_an_unknown_provider_hint_is_rejected() -> None:
    with pytest.raises(ApiError) as caught:
        await authenticator(jwt_provider()).authenticate(mint(), provider="nope")
    assert caught.value.status == 401


def test_building_without_providers_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="AUTH_PROVIDERS"):
        build_authenticator([], [])


def jwks_for(pem_public: str, kid: str) -> dict[str, Any]:
    public = serialization.load_pem_public_key(pem_public.encode())
    key = jwt.algorithms.RSAAlgorithm.to_jwk(public, as_dict=True)
    return {"keys": [{**key, "kid": kid, "use": "sig", "alg": "RS256"}]}


class Jwks:
    def __init__(self, body: dict[str, Any] | None = None, status: int = 200) -> None:
        self.body = body
        self.status = status
        self.calls: list[str] = []

    def client(self) -> httpx.AsyncClient:
        def handle(request: httpx.Request) -> httpx.Response:
            self.calls.append(str(request.url))
            if request.url.path.endswith("openid-configuration"):
                return httpx.Response(200, json={"jwks_uri": "https://idp.test/jwks"})
            return httpx.Response(self.status, json=self.body or {})

        return httpx.AsyncClient(transport=httpx.MockTransport(handle))


def jwks_verifier(jwks: Jwks, **overrides: Any) -> JwtVerifier:
    config = jwt_provider(public_key="", jwks_url="https://idp.test/jwks", **overrides)
    return JwtVerifier(config, jwks.client())


@pytest.mark.anyio
async def test_jwks_keys_are_fetched_once_and_cached() -> None:
    jwks = Jwks(jwks_for(PUBLIC_PEM, "k1"))
    verifier = jwks_verifier(jwks)
    for _ in range(3):
        assert (await verifier.verify(mint(kid="k1"))).sub == "user-1"
    assert len(jwks.calls) == 1


@pytest.mark.anyio
async def test_an_unknown_key_id_does_not_refetch_repeatedly() -> None:
    jwks = Jwks(jwks_for(PUBLIC_PEM, "k1"))
    verifier = jwks_verifier(jwks)
    await verifier.verify(mint(kid="k1"))
    for _ in range(5):
        with pytest.raises(InvalidToken):
            await verifier.verify(mint(kid="rotated"))
    assert len(jwks.calls) == 1


@pytest.mark.anyio
async def test_cached_keys_keep_working_when_a_refresh_fails() -> None:
    jwks = Jwks(jwks_for(PUBLIC_PEM, "k1"))
    verifier = jwks_verifier(jwks)
    await verifier.verify(mint(kid="k1"))
    jwks.status = 500
    verifier._fetched_at -= JWKS_TTL_SECONDS + 1
    for _ in range(3):
        assert (await verifier.verify(mint(kid="k1"))).sub == "user-1"
    assert len(jwks.calls) == 2


@pytest.mark.anyio
async def test_concurrent_first_requests_share_one_jwks_fetch() -> None:
    jwks = Jwks(jwks_for(PUBLIC_PEM, "k1"))
    verifier = jwks_verifier(jwks)
    await asyncio.gather(*(verifier.verify(mint(kid="k1")) for _ in range(10)))
    assert len(jwks.calls) == 1


@pytest.mark.anyio
async def test_a_token_without_a_key_id_is_rejected_for_jwks_providers() -> None:
    verifier = jwks_verifier(Jwks(jwks_for(PUBLIC_PEM, "k1")))
    with pytest.raises(InvalidToken):
        await verifier.verify(mint())


@pytest.mark.anyio
async def test_a_foreign_issuer_never_triggers_a_fetch() -> None:
    jwks = Jwks(jwks_for(PUBLIC_PEM, "k1"))
    with pytest.raises(InvalidToken):
        await jwks_verifier(jwks).verify(mint(issuer="https://evil.test", kid="k1"))
    assert jwks.calls == []


@pytest.mark.anyio
async def test_jwks_are_discovered_from_the_issuer() -> None:
    jwks = Jwks(jwks_for(PUBLIC_PEM, "k1"))
    config = jwt_provider(public_key="")
    verifier = JwtVerifier(config, jwks.client())
    await verifier.verify(mint(kid="k1"))
    assert jwks.calls[0].endswith("/.well-known/openid-configuration")


@pytest.mark.anyio
async def test_an_unreachable_jwks_endpoint_is_reported_as_unavailable() -> None:
    verifier = jwks_verifier(Jwks(status=500))
    with pytest.raises(ProviderUnavailable):
        await verifier.verify(mint(kid="k1"))


@pytest.mark.anyio
async def test_unavailable_provider_gives_503_not_401() -> None:
    config = jwt_provider(public_key="", jwks_url="https://idp.test/jwks")
    auth = Authenticator([config], [], Jwks(status=500).client())
    with pytest.raises(ApiError) as caught:
        await auth.authenticate(mint(kid="k1"))
    assert caught.value.status == 503


def test_a_provider_cannot_set_both_key_sources() -> None:
    with pytest.raises(ValidationError):
        jwt_provider(jwks_url="https://idp.test/jwks")


def test_public_key_accepts_escaped_newlines() -> None:
    escaped = PUBLIC_PEM.replace("\n", "\\n")
    assert jwt_provider(public_key=escaped).public_key == PUBLIC_PEM.strip()


USERINFO = UserinfoProvider(
    type="userinfo",
    name="github",
    userinfo_url="https://api.github.test/user",
    subject_field="id",
    name_field="login",
)


class Userinfo:
    def __init__(self, status: int = 200, body: dict[str, Any] | None = None) -> None:
        self.status = status
        self.body = body if body is not None else {"id": 42, "login": "octo"}
        self.requests: list[httpx.Request] = []

    def client(self) -> httpx.AsyncClient:
        def handle(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return httpx.Response(self.status, json=self.body)

        return httpx.AsyncClient(transport=httpx.MockTransport(handle))


@pytest.mark.anyio
async def test_userinfo_resolves_an_opaque_token_and_caches_it() -> None:
    fake = Userinfo()
    verifier = UserinfoVerifier(USERINFO, fake.client())
    for _ in range(2):
        identity = await verifier.verify("gho_opaque")
        assert (identity.sub, identity.name) == ("42", "octo")
    assert len(fake.requests) == 1
    assert fake.requests[0].headers["authorization"] == "Bearer gho_opaque"


@pytest.mark.anyio
async def test_userinfo_cache_evicts_only_the_oldest_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(verifiers, "USERINFO_CACHE_MAX", 2)
    fake = Userinfo()
    verifier = UserinfoVerifier(USERINFO, fake.client())
    for token in ("t1", "t2", "t3"):
        await verifier.verify(token)
    for token in ("t3", "t2"):
        await verifier.verify(token)
    assert len(fake.requests) == 3
    await verifier.verify("t1")
    assert len(fake.requests) == 4


@pytest.mark.anyio
async def test_userinfo_never_receives_a_jwt() -> None:
    fake = Userinfo()
    with pytest.raises(InvalidToken):
        await UserinfoVerifier(USERINFO, fake.client()).verify(mint())
    assert fake.requests == []


@pytest.mark.anyio
async def test_userinfo_rejection_and_outage() -> None:
    with pytest.raises(InvalidToken):
        await UserinfoVerifier(USERINFO, Userinfo(status=401).client()).verify("bad")
    with pytest.raises(ProviderUnavailable):
        await UserinfoVerifier(USERINFO, Userinfo(status=502).client()).verify("any")
    with pytest.raises(InvalidToken):
        await UserinfoVerifier(USERINFO, Userinfo(body={}).client()).verify("any")


@pytest.mark.anyio
async def test_userinfo_email_is_never_verified_so_domain_rules_fail_closed() -> None:
    fake = Userinfo(body={"id": 1, "email": "a@acme.com"})
    auth = Authenticator([USERINFO], ["acme.com"], fake.client())
    with pytest.raises(ApiError) as caught:
        await auth.authenticate("gho_opaque")
    assert caught.value.status == 403


@pytest.mark.anyio
async def test_a_jwt_provider_is_tried_before_userinfo() -> None:
    fake = Userinfo()
    auth = Authenticator([USERINFO, jwt_provider()], [], fake.client())
    principal = await auth.authenticate(mint())
    assert principal.provider == "web"
    assert fake.requests == []


def test_duplicate_provider_names_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_PROVIDERS", json.dumps([PROVIDER_CONFIG, PROVIDER_CONFIG]))
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_allowed_domains_are_split_and_normalised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ALLOWED_EMAIL_DOMAINS", "Acme.com, @other.com")
    assert Settings(_env_file=None).auth_allowed_email_domains == ["acme.com", "other.com"]


def test_the_app_refuses_to_start_without_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTH_PROVIDERS")
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None))
    with pytest.raises(RuntimeError, match="AUTH_PROVIDERS"):
        main.create_app()


@pytest.mark.anyio
@pytest.mark.parametrize(("enabled", "status"), [(False, 404), (True, 200)])
async def test_docs_routes_follow_the_setting(
    monkeypatch: pytest.MonkeyPatch, enabled: bool, status: int
) -> None:
    settings = Settings(_env_file=None, api_docs_enabled=enabled)
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    transport = httpx.ASGITransport(app=main.create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert (await c.get(path)).status_code == status
