from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentPrincipal
from app.db import get_session
from app.ratelimit import charge_new_workspace, check_new_workspace
from app.workspaces.schemas import Member
from app.workspaces.store import WorkspaceStore


def get_workspace_store(session: Annotated[AsyncSession, Depends(get_session)]) -> WorkspaceStore:
    return WorkspaceStore(session)


async def current_member(
    request: Request,
    principal: CurrentPrincipal,
    store: Annotated[WorkspaceStore, Depends(get_workspace_store)],
) -> Member:
    member = await store.find_member(principal)
    if member is not None:
        return member
    check_new_workspace(principal, request)
    member, created = await store.create_member(principal)
    if created:
        charge_new_workspace(principal, request)
    return member


CurrentMember = Annotated[Member, Depends(current_member)]
