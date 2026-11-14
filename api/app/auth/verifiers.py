"""One class per token kind. A verifier returns an Identity or raises; it applies no policy."""

import asyncio
import hashlib
import time
from typing import Any, Protocol

import httpx
import jwt

from app.auth.config import JwtProvider, UserinfoProvider
from app.auth.models import Identity

JWKS_TTL_SECONDS = 3600
JWKS_MIN_REFRESH_SECONDS = 30
USERINFO_CACHE_MAX = 1024


class InvalidToken(Exception):
    pass


class ProviderUnavailable(Exception):
    pass


class Verifier(Protocol):
    async def verify(self, token: str) -> Identity: ...


def looks_like_jwt(token: str) -> bool:
    return token.count(".") == 2


class JwtVerifier:
    def __init__(self, config: JwtProvider, http: httpx.AsyncClient) -> None:
        self._config = config
        self._http = http
        self._keys: dict[str, dict[str, Any]] = {}
        self._fetched_at = float("-inf")
        self._lock = asyncio.Lock()

    async def verify(self, token: str) -> Identity:
        if not looks_like_jwt(token):
            raise InvalidToken("not a JWT")
        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
            kid = jwt.get_unverified_header(token).get("kid")
        except jwt.PyJWTError as exc:
            raise InvalidToken("malformed token") from exc
        # A token for another issuer must never trigger a JWKS fetch here.
        if unverified.get("iss") != self._config.issuer:
            raise InvalidToken("issuer mismatch")
        try:
            claims = jwt.decode(
                token,
                await self._signing_key(kid),
                algorithms=list(self._config.algorithms),
                audience=self._config.audience,
                issuer=self._config.issuer,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidToken(str(exc)) from exc
        return Identity(
            sub=str(claims["sub"]),
            email=claims.get("email"),
            email_verified=claims.get("email_verified") is True,
            name=claims.get("name"),
        )

    async def _signing_key(self, kid: str | None) -> Any:
        if self._config.public_key:
            return self._config.public_key
        if kid is None:
            raise InvalidToken("token has no key id")
        if self._needs_refresh(kid):
            async with self._lock:
                if self._needs_refresh(kid):
                    await self._refresh()
        try:
            return jwt.PyJWK.from_dict(self._keys[kid]).key
        except KeyError:
            raise InvalidToken("unknown signing key") from None

    def _needs_refresh(self, kid: str) -> bool:
        age = time.monotonic() - self._fetched_at
        # Unknown kid: refetch, but rate-limited so junk tokens cannot hammer the JWKS endpoint.
        return age > JWKS_TTL_SECONDS or (kid not in self._keys and age > JWKS_MIN_REFRESH_SECONDS)

    async def _refresh(self) -> None:
        try:
            await self._fetch_keys()
        except ProviderUnavailable:
            if not self._keys:
                raise
            # Keep serving with the cached keys; retry after the minimum interval, not per request.
            self._fetched_at = time.monotonic() - JWKS_TTL_SECONDS + JWKS_MIN_REFRESH_SECONDS

    async def _fetch_keys(self) -> None:
        try:
            url = self._config.jwks_url or await self._discover()
            response = await self._http.get(url)
            response.raise_for_status()
            keys = response.json()["keys"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise ProviderUnavailable(self._config.name) from exc
        self._keys = {k["kid"]: k for k in keys if "kid" in k}
        self._fetched_at = time.monotonic()

    async def _discover(self) -> str:
        url = self._config.issuer.rstrip("/") + "/.well-known/openid-configuration"
        response = await self._http.get(url)
        response.raise_for_status()
        return response.json()["jwks_uri"]


class UserinfoVerifier:
    def __init__(self, config: UserinfoProvider, http: httpx.AsyncClient) -> None:
        self._config = config
        self._http = http
        self._cache: dict[str, tuple[float, Identity]] = {}

    async def verify(self, token: str) -> Identity:
        # A JWT belongs to a JWT provider and must never be sent to a third-party endpoint.
        if looks_like_jwt(token):
            raise InvalidToken("not an opaque token")
        digest = hashlib.sha256(token.encode()).hexdigest()
        cached = self._cache.get(digest)
        if cached is not None and cached[0] > time.monotonic():
            return cached[1]
        identity = await self._fetch(token)
        if self._config.cache_seconds:
            if len(self._cache) >= USERINFO_CACHE_MAX:
                del self._cache[next(iter(self._cache))]
            self._cache[digest] = (time.monotonic() + self._config.cache_seconds, identity)
        return identity

    async def _fetch(self, token: str) -> Identity:
        try:
            response = await self._http.get(
                self._config.userinfo_url,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(self._config.name) from exc
        if response.status_code in (401, 403):
            raise InvalidToken("rejected by provider")
        try:
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderUnavailable(self._config.name) from exc
        sub = data.get(self._config.subject_field)
        if sub is None:
            raise InvalidToken("no subject in userinfo")
        return Identity(
            sub=str(sub),
            email=data.get(self._config.email_field),
            email_verified=data.get("email_verified") is True,
            name=data.get(self._config.name_field),
        )
