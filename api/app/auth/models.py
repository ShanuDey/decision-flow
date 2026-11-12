from app.engine.base import FrozenBaseModel


class Identity(FrozenBaseModel):
    """What a verifier proves about a token, before any policy is applied."""

    sub: str
    email: str | None = None
    email_verified: bool = False
    name: str | None = None


class Principal(FrozenBaseModel):
    sub: str
    provider: str
    email: str | None = None
    name: str | None = None
