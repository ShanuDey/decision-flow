"""A connection as one run uses it: the headers to send and the hosts they may go to."""

import re

from pydantic import Field, SecretStr

from app.engine.base import FrozenBaseModel

HOST = re.compile(
    r"(\*\.)?[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*"
)


class ResolvedConnection(FrozenBaseModel):
    id: str
    name: str
    headers: dict[str, SecretStr] = Field(default_factory=dict)
    hosts: list[str] = Field(default_factory=list)
    # Plain (non-secret) field values, read in templates as `{{ connection.NAME }}`.
    values: dict[str, str] = Field(default_factory=dict)
    # Every secret value, so the redactor can mask it wherever it turns up.
    secret_values: list[SecretStr] = Field(default_factory=list)


def host_allowed(host: str, patterns: list[str]) -> bool:
    host = host.lower().rstrip(".")
    for pattern in patterns:
        if pattern.startswith("*."):
            if host.endswith(pattern[1:]) and host != pattern[2:]:
                return True
        elif host == pattern:
            return True
    return False
