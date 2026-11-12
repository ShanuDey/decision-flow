"""Throwaway signing key for tests. Importing this trusts its public key in AUTH_PROVIDERS."""

import json
import os
import time
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER = "https://web.test"
AUDIENCE = "decision-flow-api"
PROVIDER = "web"

_PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE_PEM = _PRIVATE.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode()
PUBLIC_PEM = (
    _PRIVATE.public_key()
    .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    .decode()
)

PROVIDER_CONFIG: dict[str, Any] = {
    "type": "jwt",
    "name": PROVIDER,
    "issuer": ISSUER,
    "audience": AUDIENCE,
    "public_key": PUBLIC_PEM,
}

os.environ["AUTH_PROVIDERS"] = json.dumps([PROVIDER_CONFIG])


def mint(
    sub: str = "user-1",
    *,
    issuer: str = ISSUER,
    audience: str = AUDIENCE,
    expires_in: int = 300,
    key: str = PRIVATE_PEM,
    algorithm: str = "RS256",
    kid: str | None = None,
    **claims: Any,
) -> str:
    payload = {
        "sub": sub,
        "iss": issuer,
        "aud": audience,
        "exp": int(time.time()) + expires_in,
        **claims,
    }
    headers = {"kid": kid} if kid else None
    return jwt.encode(payload, key, algorithm=algorithm, headers=headers)


def bearer(token: str | None = None, **kwargs: Any) -> dict[str, str]:
    return {"Authorization": f"Bearer {token or mint(**kwargs)}"}
