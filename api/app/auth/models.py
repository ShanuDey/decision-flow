from typing import Literal

from app.engine.base import FrozenBaseModel


class Identity(FrozenBaseModel):
    """What a verifier proves about a token, before any policy is applied."""

    sub: str
    email: str | None = None
    email_verified: bool = False
    name: str | None = None


class AppConfig(FrozenBaseModel):
    """Deployment settings the web app needs to word its screens."""

    delete_mode: Literal["hard", "soft"]


class Principal(FrozenBaseModel):
    sub: str
    provider: str
    email: str | None = None
    name: str | None = None
