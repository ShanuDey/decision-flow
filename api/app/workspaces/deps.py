from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentPrincipal
from app.db import get_session
from app.workspaces.schemas import Member
from app.workspaces.store import WorkspaceStore


def get_workspace_store(session: Annotated[AsyncSession, Depends(get_session)]) -> WorkspaceStore:
    return WorkspaceStore(session)


async def current_member(
    principal: CurrentPrincipal,
    store: Annotated[WorkspaceStore, Depends(get_workspace_store)],
) -> Member:
    return await store.ensure_member(principal)


CurrentMember = Annotated[Member, Depends(current_member)]
