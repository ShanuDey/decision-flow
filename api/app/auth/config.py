from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from app.engine.base import FrozenBaseModel

Algorithm = Literal["RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256", "EdDSA"]


class JwtProvider(FrozenBaseModel):
    """A signed-JWT issuer. Keys come from public_key, jwks_url, or the issuer's OIDC metadata."""

    type: Literal["jwt"]
    name: str
    issuer: str
    audience: str
    jwks_url: str = ""
    public_key: str = ""  # PEM; "\n" escapes allowed so it fits on one env line
    algorithms: tuple[Algorithm, ...] = ("RS256", "ES256")

    @field_validator("public_key")
    @classmethod
    def _unescape_newlines(cls, pem: str) -> str:
        return pem.replace("\\n", "\n").strip()

    @model_validator(mode="after")
    def _one_key_source(self) -> "JwtProvider":
        if self.jwks_url and self.public_key:
            raise ValueError(f"provider {self.name!r}: set jwks_url or public_key, not both")
        return self


class UserinfoProvider(FrozenBaseModel):
    """An opaque-token provider checked by calling its user endpoint (GitHub)."""

    type: Literal["userinfo"]
    name: str
    userinfo_url: str
    subject_field: str = "sub"
    email_field: str = "email"
    name_field: str = "name"
    cache_seconds: int = Field(default=300, ge=0)


ProviderConfig = Annotated[JwtProvider | UserinfoProvider, Field(discriminator="type")]
