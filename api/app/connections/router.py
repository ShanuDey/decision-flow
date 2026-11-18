"""HTTP only: parsing, status codes, response shapes. Logic lives in service.py."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.connections import service
from app.connections.schemas import (
    ConnectionCreate,
    ConnectionList,
    ConnectionSummary,
    ConnectionTest,
    ConnectionTypeList,
    ConnectionUpdate,
)
from app.connections.store import ConnectionStore, get_connection_store
from app.errors import ErrorResponse
from app.limits import Limits, get_limits
from app.secrets.crypto import BoxFactory, SecretBox, get_box, get_box_factory
from app.security.policy import outbound_policy
from app.settings import Settings, get_settings
from app.workspaces.deps import CurrentMember

router = APIRouter(tags=["connections"])
Store = Annotated[ConnectionStore, Depends(get_connection_store)]
Box = Annotated[SecretBox, Depends(get_box)]

NOT_FOUND = {404: {"model": ErrorResponse}}
CONFLICT = {409: {"model": ErrorResponse}}
INVALID = {422: {"model": ErrorResponse}}
UNAVAILABLE = {503: {"model": ErrorResponse}}


@router.get("/connection-types")
async def list_connection_types() -> ConnectionTypeList:
    """Lists the connection types you can create, with the fields each one asks for."""
    return ConnectionTypeList(items=service.type_infos())


@router.get("/connections")
async def list_connections(store: Store, member: CurrentMember) -> ConnectionList:
    """Lists the workspace's connections. Secret values are never returned."""
    rows = await store.list_connections(member)
    return ConnectionList(items=[service.summarize(r) for r in rows])


@router.post(
    "/connections",
    status_code=status.HTTP_201_CREATED,
    responses={**CONFLICT, **INVALID, **UNAVAILABLE},
)
async def create_connection(
    body: ConnectionCreate,
    store: Store,
    box: Box,
    member: CurrentMember,
    limits: Annotated[Limits, Depends(get_limits)],
) -> ConnectionSummary:
    """Creates a connection of a given type.

    Its secret fields are encrypted and cannot be read back. It can only be used for the hosts
    it allows.
    """
    return service.summarize(await service.create_connection(store, box, member, body, limits))


@router.patch(
    "/connections/{connection_id}",
    responses={**NOT_FOUND, **CONFLICT, **INVALID, **UNAVAILABLE},
)
async def update_connection(
    connection_id: uuid.UUID,
    body: ConnectionUpdate,
    store: Store,
    box: Box,
    member: CurrentMember,
) -> ConnectionSummary:
    """Renames a connection or changes fields. A secret field you leave out keeps its value."""
    updated = await service.update_connection(store, box, member, connection_id, body)
    return service.summarize(updated)


@router.delete(
    "/connections/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**NOT_FOUND, **CONFLICT},
)
async def delete_connection(
    connection_id: uuid.UUID, store: Store, member: CurrentMember, force: bool = False
) -> None:
    """Removes a connection for good.

    409 `connection_in_use` lists the flows that use it; `force=true` deletes it anyway.
    """
    await service.delete_connection(store, member, connection_id, force=force)


@router.post(
    "/connections/{connection_id}/test",
    responses={**NOT_FOUND, **INVALID, **UNAVAILABLE},
)
async def test_connection(
    connection_id: uuid.UUID,
    store: Store,
    make_box: Annotated[BoxFactory, Depends(get_box_factory)],
    member: CurrentMember,
    limits: Annotated[Limits, Depends(get_limits)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConnectionTest:
    """Calls the service's check endpoint with the saved credentials.

    Only types that have one can be tested, otherwise 422 `no_test_available`. The answer says
    whether the service accepted the credentials, and never includes what it sent back.
    """
    return await service.test_connection(
        store, make_box, member, connection_id, outbound_policy(settings, limits)
    )
