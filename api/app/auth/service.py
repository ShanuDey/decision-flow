import httpx

from app.auth.config import JwtProvider, ProviderConfig
from app.auth.models import Identity, Principal
from app.auth.verifiers import (
    InvalidToken,
    JwtVerifier,
    ProviderUnavailable,
    UserinfoVerifier,
    Verifier,
)
from app.errors import ApiError

HTTP_TIMEOUT_SECONDS = 5.0


def unauthenticated(message: str) -> ApiError:
    return ApiError(401, "unauthenticated", message, headers={"WWW-Authenticate": "Bearer"})


def _verifier_for(provider: ProviderConfig, http: httpx.AsyncClient) -> Verifier:
    if isinstance(provider, JwtProvider):
        return JwtVerifier(provider, http)
    return UserinfoVerifier(provider, http)


class Authenticator:
    def __init__(
        self,
        providers: list[ProviderConfig],
        allowed_email_domains: list[str],
        http: httpx.AsyncClient,
    ) -> None:
        self._http = http
        self._allowed_domains = frozenset(allowed_email_domains)
        # JWT providers first: they verify locally and never forward the token anywhere.
        ordered = sorted(providers, key=lambda p: not isinstance(p, JwtProvider))
        self._verifiers = {p.name: _verifier_for(p, http) for p in ordered}

    async def aclose(self) -> None:
        await self._http.aclose()

    async def authenticate(self, token: str, provider: str | None = None) -> Principal:
        if provider is not None and provider not in self._verifiers:
            raise unauthenticated("Unknown auth provider")
        candidates = [provider] if provider is not None else list(self._verifiers)
        unavailable = False
        for name in candidates:
            try:
                identity = await self._verifiers[name].verify(token)
            except InvalidToken:
                continue
            except ProviderUnavailable:
                unavailable = True
                continue
            self._check_domain(identity)
            return Principal(
                sub=identity.sub, provider=name, email=identity.email, name=identity.name
            )
        if unavailable:
            raise ApiError(503, "auth_unavailable", "Identity provider is unreachable")
        raise unauthenticated("Invalid or expired token")

    def _check_domain(self, identity: Identity) -> None:
        if not self._allowed_domains:
            return
        domain = identity.email.rpartition("@")[2].lower() if identity.email else ""
        if not identity.email_verified or domain not in self._allowed_domains:
            raise ApiError(403, "forbidden_domain", "This account is not allowed here")


def build_authenticator(
    providers: list[ProviderConfig], allowed_email_domains: list[str]
) -> Authenticator:
    if not providers:
        raise RuntimeError("Auth is always on: set AUTH_PROVIDERS to at least one provider")
    return Authenticator(
        providers, allowed_email_domains, httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)
    )
