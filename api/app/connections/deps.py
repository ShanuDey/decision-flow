"""The connection types the current workspace can use."""

from collections.abc import Mapping
from typing import Annotated

from fastapi import Depends

from app.catalog.service import connection_types
from app.catalog.store import InstalledStore, get_installed_store
from app.connections.types import ConnectionType
from app.workspaces.deps import CurrentMember


async def get_types(
    member: CurrentMember,
    installed: Annotated[InstalledStore, Depends(get_installed_store)],
) -> Mapping[str, ConnectionType]:
    return await connection_types(installed, member)


Types = Annotated[Mapping[str, ConnectionType], Depends(get_types)]
