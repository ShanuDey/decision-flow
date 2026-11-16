from datetime import datetime
from typing import Annotated

from fastapi import Path
from pydantic import StringConstraints

from app.engine.base import FrozenBaseModel

NAME_PATTERN = r"^[A-Z][A-Z0-9_]{0,63}$"
MIN_VALUE_LENGTH = 8

SecretNameParam = Annotated[str, Path(pattern=NAME_PATTERN)]


class SecretPut(FrozenBaseModel):
    # Not stripped: a value is stored exactly as given.
    value: Annotated[str, StringConstraints(min_length=MIN_VALUE_LENGTH, max_length=4096)]


class SecretSummary(FrozenBaseModel):
    name: str
    created_at: datetime
    updated_at: datetime


class SecretList(FrozenBaseModel):
    items: list[SecretSummary]
