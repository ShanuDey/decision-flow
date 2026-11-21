"""Connection use cases. No HTTP types except ApiError."""

import json
import uuid
from collections.abc import Mapping

from cryptography.fernet import InvalidToken

from app.connections.catalog import BY_ID, TYPES
from app.connections.models import Connection
from app.connections.schemas import (
    MAX_VALUE_LENGTH,
    MIN_SECRET_LENGTH,
    ConnectionCreate,
    ConnectionSummary,
    ConnectionTest,
    ConnectionTypeInfo,
    ConnectionUpdate,
    FieldInfo,
)
from app.connections.store import ConnectionStore, NameTaken
from app.connections.types import (
    ConnectionType,
    hosts_of,
    resolve,
    test_target,
    url_host,
    with_defaults,
)
from app.engine.connections import ResolvedConnection
from app.errors import ApiError
from app.limits import Limits
from app.secrets.crypto import BoxFactory, SecretBox
from app.security.ssrf import OutboundError, OutboundPolicy, fetch
from app.workspaces.schemas import Member


def ordered(types: Mapping[str, ConnectionType]) -> list[ConnectionType]:
    """Built-in types in their shipped order, then the installed ones by name."""
    built_in = [t for t in TYPES if t.id in types]
    installed = sorted((t for t in types.values() if t.id not in BY_ID), key=lambda t: t.name)
    return [*built_in, *installed]


def type_infos(types: Mapping[str, ConnectionType]) -> list[ConnectionTypeInfo]:
    return [
        ConnectionTypeInfo(
            id=t.id,
            name=t.name,
            description=t.description,
            icon=t.icon,
            docs_url=t.docs_url,
            category=t.category,
            source="builtin" if t.id in BY_ID else "installed",
            fields=[FieldInfo(**f.model_dump()) for f in t.fields],
            hosts=t.fixed_hosts,
            hosts_from=t.hosts_from or "",
            testable=bool(t.test_url or t.test_path),
        )
        for t in ordered(types)
    ]


def summarize(connection: Connection, types: Mapping[str, ConnectionType]) -> ConnectionSummary:
    kind = types.get(connection.type)
    return ConnectionSummary(
        id=connection.id,
        name=connection.name,
        type=connection.type,
        config=connection.config,
        secrets_set=[f.name for f in kind.fields if f.secret] if kind else [],
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )


def invalid(message: str, field: str | None = None) -> ApiError:
    return ApiError(422, "invalid_connection", message, {"field": field})


def not_found() -> ApiError:
    return ApiError(404, "not_found", "Connection not found")


def name_taken() -> ApiError:
    return ApiError(409, "connection_name_taken", "You already have a connection with that name.")


def require_type(type_id: str, types: Mapping[str, ConnectionType]) -> ConnectionType:
    kind = types.get(type_id)
    if kind is None:
        raise ApiError(422, "unknown_connection_type", f"Unknown connection type '{type_id}'")
    return kind


def _check_values(kind: ConnectionType, values: dict[str, str]) -> None:
    for name, value in values.items():
        spec = kind.field(name)
        if spec is None:
            raise invalid(f"{kind.name} has no field '{name}'", name)
        if len(value) > MAX_VALUE_LENGTH:
            raise invalid(f"{spec.label} is too long", name)
        if spec.secret and value and len(value) < MIN_SECRET_LENGTH:
            raise invalid(f"{spec.label} must be at least {MIN_SECRET_LENGTH} characters", name)
        if spec.format == "url" and value.strip():
            try:
                url_host(value)
            except ValueError as exc:
                raise invalid(f"{spec.label}: {exc}", name) from None


def _check_complete(kind: ConnectionType, merged: dict[str, str]) -> None:
    for spec in kind.fields:
        if spec.required and not merged.get(spec.name, "").strip():
            raise invalid(f"{spec.label} is required", spec.name)
    try:
        hosts_of(kind, merged)
    except ValueError as exc:
        raise invalid(str(exc), "hosts") from None


def _split(kind: ConnectionType, merged: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    config: dict[str, str] = {}
    secrets: dict[str, str] = {}
    for spec in kind.fields:
        value = merged.get(spec.name, "")
        if not value:
            continue
        if spec.secret:
            secrets[spec.name] = value
        else:
            config[spec.name] = value.strip()
    return config, secrets


def read_secrets(box: SecretBox, connection: Connection) -> dict[str, str]:
    try:
        return json.loads(box.decrypt(connection.secrets_encrypted))
    except InvalidToken:
        raise ApiError(
            500,
            "connection_unreadable",
            f"Connection {connection.name} cannot be decrypted; ENCRYPTION_KEY may have changed.",
            {"id": str(connection.id)},
        ) from None


async def create_connection(
    store: ConnectionStore,
    box: SecretBox,
    member: Member,
    body: ConnectionCreate,
    limits: Limits,
    types: Mapping[str, ConnectionType],
) -> Connection:
    cap = limits.max_connections_per_workspace
    if cap and (count := await store.count(member)) >= cap:
        raise ApiError(
            409,
            "connection_limit_reached",
            f"You have {count} connections; the limit is {cap}.",
            {"limit": cap, "count": count, **limits.notice_details()},
        )
    kind = require_type(body.type, types)
    _check_values(kind, body.values)
    values = with_defaults(kind, body.values)
    _check_complete(kind, values)
    config, secrets = _split(kind, values)
    try:
        return await store.add(member, kind.id, body.name, config, box.encrypt(json.dumps(secrets)))
    except NameTaken:
        raise name_taken() from None


async def update_connection(
    store: ConnectionStore,
    box: SecretBox,
    member: Member,
    connection_id: uuid.UUID,
    body: ConnectionUpdate,
    types: Mapping[str, ConnectionType],
) -> Connection:
    connection = await store.get(member, connection_id)
    if connection is None:
        raise not_found()
    kind = require_type(connection.type, types)
    _check_values(kind, body.values)
    merged = with_defaults(
        kind, {**connection.config, **read_secrets(box, connection), **body.values}
    )
    _check_complete(kind, merged)
    config, secrets = _split(kind, merged)
    try:
        updated = await store.replace(
            member,
            connection_id,
            body.name or connection.name,
            config,
            box.encrypt(json.dumps(secrets)),
        )
    except NameTaken:
        raise name_taken() from None
    if updated is None:
        raise not_found()
    return updated


async def refuse_if_used(
    store: ConnectionStore, member: Member, connection_id: uuid.UUID, force: bool
) -> None:
    flows = [] if force else await store.flows_using(member, connection_id)
    if flows:
        raise ApiError(
            409,
            "connection_in_use",
            "Flows use this connection; they will fail until you pick another",
            {"flows": [{"id": str(f.id), "name": f.name} for f in flows]},
        )


async def delete_connection(
    store: ConnectionStore, member: Member, connection_id: uuid.UUID, *, force: bool
) -> None:
    if await store.get(member, connection_id) is None:
        raise not_found()
    await refuse_if_used(store, member, connection_id, force)
    if not await store.delete(member, connection_id):
        raise not_found()


async def load_run_connections(
    store: ConnectionStore,
    make_box: BoxFactory,
    member: Member,
    ids: set[str],
    types: Mapping[str, ConnectionType],
) -> dict[str, ResolvedConnection]:
    wanted: dict[uuid.UUID, str] = {}
    for raw in ids:
        try:
            wanted[uuid.UUID(raw)] = raw
        except ValueError:
            raise ApiError(
                422, "connection_not_found", f"Connection {raw} not found", {"ids": [raw]}
            ) from None
    found = {c.id: c for c in await store.get_many(member, set(wanted))}
    if missing := sorted(str(i) for i in wanted if i not in found):
        raise ApiError(
            422,
            "connection_not_found",
            "A connection this flow uses no longer exists; pick another in the node.",
            {"ids": missing},
        )
    box = make_box()
    return {
        str(c.id): resolve(
            require_type(c.type, types), str(c.id), c.name, {**c.config, **read_secrets(box, c)}
        )
        for c in found.values()
    }


async def test_connection(
    store: ConnectionStore,
    make_box: BoxFactory,
    member: Member,
    connection_id: uuid.UUID,
    policy: OutboundPolicy,
    types: Mapping[str, ConnectionType],
) -> ConnectionTest:
    connection = await store.get(member, connection_id)
    if connection is None:
        raise not_found()
    kind = require_type(connection.type, types)
    values = {**connection.config, **read_secrets(make_box(), connection)}
    target = test_target(kind, values)
    if target is None:
        raise ApiError(
            422, "no_test_available", f"{kind.name} has no built-in test; try it in a flow."
        )
    resolved = resolve(kind, str(connection.id), connection.name, values)
    headers = {name: value.get_secret_value() for name, value in resolved.headers.items()}
    try:
        response = await fetch(policy, "GET", target, headers=headers)
    except OutboundError as exc:
        return ConnectionTest(
            ok=False, status=None, message=f"Could not reach the service: {exc.message}"
        )
    ok = 200 <= response.status_code < 300
    message = "The service accepted the credentials." if ok else _rejection(response.status_code)
    return ConnectionTest(ok=ok, status=response.status_code, message=message)


def _rejection(status: int) -> str:
    if status in (401, 403):
        return "The service rejected the credentials."
    return f"The service answered HTTP {status}."
