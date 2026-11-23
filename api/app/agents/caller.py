from typing import Annotated, Literal

from fastapi import Depends, Header

from app.engine.base import FrozenBaseModel
from app.errors import ApiError

EXTERNAL_ID_MAX = 256
# Ids we generate for callers that name nobody.
ANON_PREFIX = "anon-"


class Caller(FrozenBaseModel):
    source: Literal["web", "api"]
    external_user_id: str | None


def clean_external_id(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    if (
        not trimmed
        or len(trimmed) > EXTERNAL_ID_MAX
        or any(ord(c) < 32 or ord(c) == 127 for c in trimmed)
    ):
        raise ApiError(
            422,
            "invalid_external_user_id",
            f"An external user id is 1 to {EXTERNAL_ID_MAX} characters without control characters",
        )
    return trimmed


def get_caller(
    x_df_source: Annotated[str | None, Header()] = None,
    x_external_user_id: Annotated[str | None, Header()] = None,
) -> Caller:
    # Only the gateway sets the source header: the web proxy forwards an allowlist of headers.
    if x_df_source != "api":
        return Caller(source="web", external_user_id=None)
    return Caller(source="api", external_user_id=clean_external_id(x_external_user_id))


CurrentCaller = Annotated[Caller, Depends(get_caller)]
