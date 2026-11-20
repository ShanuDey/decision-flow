"""What a connection type is, and how one signs a request. The types themselves are JSON data."""

import base64
import re
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator

from app.engine.base import FrozenBaseModel
from app.engine.connections import HOST, ResolvedConnection
from app.security.links import DocsUrl

HOSTS_FIELD = "hosts"
MAX_HOSTS = 10


class FieldSpec(FrozenBaseModel):
    name: str
    label: str
    secret: bool = False
    required: bool = True
    help: str = ""
    format: Literal["text", "url"] = "text"
    default: str = ""
    placeholder: str = ""


class Bearer(FrozenBaseModel):
    kind: Literal["bearer"] = "bearer"
    token: str


class Basic(FrozenBaseModel):
    kind: Literal["basic"] = "basic"
    username: str
    password: str


class Header(FrozenBaseModel):
    kind: Literal["header"] = "header"
    name_field: str
    value: str


Auth = Annotated[Bearer | Basic | Header, Field(discriminator="kind")]


TYPE_ID = re.compile(r"[a-z][a-z0-9_]{0,63}")


class ConnectionType(FrozenBaseModel):
    schema_version: Literal[1] = 1
    version: str = Field("1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    id: str
    name: str
    description: str
    fields: list[FieldSpec]
    auth: Auth
    icon: str = "plug"
    docs_url: DocsUrl = ""
    category: Literal["builtin", "custom"] = "builtin"
    # Allowed hosts: fixed, the host of the `hosts_from` URL field, or listed in `hosts`.
    fixed_hosts: list[str] = Field(default_factory=list)
    hosts_from: str | None = None
    test_url: str | None = None
    # Appended to the `hosts_from` URL for the test call.
    test_path: str | None = None

    def field(self, name: str) -> FieldSpec | None:
        return next((f for f in self.fields if f.name == name), None)

    @model_validator(mode="after")
    def _check_references(self) -> Self:
        """A file is data, so every name it points at must exist and be the right kind."""
        problems: list[str] = []
        if not TYPE_ID.fullmatch(self.id):
            problems.append("id must be lowercase letters, digits and underscores")
        names = [f.name for f in self.fields]
        if len(set(names)) != len(names):
            problems.append("field names must be unique")

        def need(name: str, role: str, *, secret: bool | None = None) -> None:
            spec = self.field(name)
            if spec is None:
                problems.append(f"{role} '{name}' is not a field")
            elif secret is not None and spec.secret != secret:
                problems.append(f"{role} '{name}' must{'' if secret else ' not'} be a secret field")

        auth = self.auth
        if isinstance(auth, Bearer):
            need(auth.token, "token", secret=True)
        elif isinstance(auth, Basic):
            need(auth.username, "username", secret=False)
            need(auth.password, "password", secret=True)
        else:
            need(auth.name_field, "name_field", secret=False)
            need(auth.value, "value", secret=True)

        sources = [bool(self.fixed_hosts), self.hosts_from is not None]
        if all(sources):
            problems.append("use fixed_hosts or hosts_from, not both")
        if self.hosts_from is not None:
            spec = self.field(self.hosts_from)
            if spec is None or spec.format != "url":
                problems.append(f"hosts_from '{self.hosts_from}' must be a url field")
        elif not self.fixed_hosts and self.field(HOSTS_FIELD) is None:
            problems.append(f"add a '{HOSTS_FIELD}' field, fixed_hosts or hosts_from")
        if bad := next((h for h in self.fixed_hosts if not HOST.fullmatch(h)), None):
            problems.append(f"fixed host '{bad}' is not a host name")
        if self.test_path and self.hosts_from is None:
            problems.append("test_path needs hosts_from")
        if problems:
            raise ValueError("; ".join(problems))
        return self


def parse_hosts(raw: str) -> list[str]:
    hosts = [h.strip().lower() for h in raw.split(",") if h.strip()]
    if not hosts:
        raise ValueError("list at least one host")
    if len(hosts) > MAX_HOSTS:
        raise ValueError(f"list at most {MAX_HOSTS} hosts")
    if bad := next((h for h in hosts if not HOST.fullmatch(h)), None):
        raise ValueError(f"'{bad}' is not a host name; leave out the scheme, port and path")
    return hosts


def url_host(value: str) -> str:
    parts = urlsplit(value.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("enter a full URL starting with http:// or https://")
    if parts.username or parts.password:
        raise ValueError("leave credentials out of the URL")
    return parts.hostname.lower()


def with_defaults(kind: ConnectionType, values: dict[str, str]) -> dict[str, str]:
    filled = dict(values)
    for spec in kind.fields:
        if spec.default and not filled.get(spec.name, "").strip():
            filled[spec.name] = spec.default
    return filled


def hosts_of(kind: ConnectionType, values: dict[str, str]) -> list[str]:
    if kind.fixed_hosts:
        return list(kind.fixed_hosts)
    if kind.hosts_from:
        return [url_host(with_defaults(kind, values).get(kind.hosts_from, ""))]
    return parse_hosts(values.get(HOSTS_FIELD, ""))


def test_target(kind: ConnectionType, values: dict[str, str]) -> str | None:
    if kind.test_url:
        return kind.test_url
    if kind.test_path and kind.hosts_from:
        base = with_defaults(kind, values).get(kind.hosts_from, "")
        return base.strip().rstrip("/") + kind.test_path
    return None


def _headers(kind: ConnectionType, values: dict[str, str]) -> dict[str, str]:
    auth = kind.auth
    if isinstance(auth, Bearer):
        return {"Authorization": f"Bearer {values[auth.token]}"}
    if isinstance(auth, Basic):
        pair = f"{values[auth.username]}:{values[auth.password]}".encode()
        return {"Authorization": f"Basic {base64.b64encode(pair).decode()}"}
    return {values[auth.name_field]: values[auth.value]}


def resolve(
    kind: ConnectionType, connection_id: str, name: str, values: dict[str, str]
) -> ResolvedConnection:
    headers = _headers(kind, values)
    # The encoded header (Basic is base64) can be echoed back by a server, so it is masked too.
    secret_values = [
        SecretStr(values[f.name]) for f in kind.fields if f.secret and f.name in values
    ]
    secret_values += [SecretStr(v) for v in headers.values()]
    return ResolvedConnection(
        id=connection_id,
        name=name,
        headers={k: SecretStr(v) for k, v in headers.items()},
        hosts=hosts_of(kind, values),
        secret_values=secret_values,
    )
