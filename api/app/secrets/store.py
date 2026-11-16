"""Persistence for secrets. Tests swap this class for an in-memory fake."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.secrets.models import Secret
from app.workspaces.schemas import Member


class SecretStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_secrets(self, member: Member) -> list[Secret]:
        rows = await self.session.scalars(
            select(Secret).where(Secret.workspace_id == member.workspace_id).order_by(Secret.name)
        )
        return list(rows)

    async def count(self, member: Member) -> int:
        return (
            await self.session.scalar(
                select(func.count())
                .select_from(Secret)
                .where(Secret.workspace_id == member.workspace_id)
            )
            or 0
        )

    async def exists(self, member: Member, name: str) -> bool:
        found = await self.session.scalar(
            select(Secret.id).where(Secret.workspace_id == member.workspace_id, Secret.name == name)
        )
        return found is not None

    async def put(self, member: Member, name: str, encrypted: str) -> Secret:
        stmt = (
            insert(Secret)
            .values(
                workspace_id=member.workspace_id,
                name=name,
                value_encrypted=encrypted,
                created_by=member.user_id,
                updated_by=member.user_id,
            )
            .on_conflict_do_update(
                index_elements=[Secret.workspace_id, Secret.name],
                set_={
                    "value_encrypted": encrypted,
                    "updated_by": member.user_id,
                    "updated_at": func.now(),
                },
            )
            .returning(Secret)
            .execution_options(populate_existing=True)
        )
        secret = await self.session.scalar(stmt)
        await self.session.commit()
        assert secret is not None
        return secret

    async def delete(self, member: Member, name: str) -> bool:
        result = await self.session.execute(
            delete(Secret)
            .where(Secret.workspace_id == member.workspace_id, Secret.name == name)
            .returning(Secret.id)
        )
        await self.session.commit()
        return result.first() is not None


def get_secret_store(session: Annotated[AsyncSession, Depends(get_session)]) -> SecretStore:
    return SecretStore(session)
