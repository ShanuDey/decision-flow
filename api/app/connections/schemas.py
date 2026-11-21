import uuid
from datetime import datetime
from typing import Annotated

from pydantic import StringConstraints

from app.engine.base import FrozenBaseModel

ConnectionName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
]
MIN_SECRET_LENGTH = 8
MAX_VALUE_LENGTH = 4096


class FieldInfo(FrozenBaseModel):
    name: str
    label: str
    secret: bool
    required: bool
    help: str
    format: str
    default: str
    placeholder: str


class ConnectionTypeInfo(FrozenBaseModel):
    id: str
    name: str
    description: str
    icon: str
    docs_url: str
    # "builtin" ships with the app; "custom" is a generic type for services nobody has packaged.
    category: str
    # "builtin" ships with the app; "installed" came from the Marketplace.
    source: str
    fields: list[FieldInfo]
    # The fixed hosts, or empty when the user lists them in the `hosts` field.
    hosts: list[str]
    # The URL field whose host is the only one allowed, or empty.
    hosts_from: str
    testable: bool


class ConnectionTypeList(FrozenBaseModel):
    items: list[ConnectionTypeInfo]


class ConnectionCreate(FrozenBaseModel):
    type: str
    name: ConnectionName
    # Field name to value. Secret fields are encrypted and cannot be read back.
    values: dict[str, str]


class ConnectionUpdate(FrozenBaseModel):
    name: ConnectionName | None = None
    # Only the fields you send change; a secret field you leave out keeps its value.
    values: dict[str, str] = {}


class ConnectionSummary(FrozenBaseModel):
    id: uuid.UUID
    name: str
    type: str
    # The plain field values; secret fields are never returned.
    config: dict[str, str]
    # The type's secret fields; their values are never returned.
    secrets_set: list[str]
    created_at: datetime
    updated_at: datetime


class ConnectionList(FrozenBaseModel):
    items: list[ConnectionSummary]


class ConnectionTest(FrozenBaseModel):
    ok: bool
    # The status the service answered with; null when the request could not be made.
    status: int | None
    message: str
