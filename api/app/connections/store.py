"""Persistence for connections. Tests swap this class for an in-memory fake."""

import uuid
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.connections.models import Connection
from app.db import get_session
from app.flows.models import Flow, FlowVersion
from app.workspaces.schemas import Member


class NameTaken(Exception):
    pass


class ConnectionStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_connections(self, member: Member) -> list[Connection]:
        rows = await self.session.scalars(
            select(Connection)
            .where(Connection.workspace_id == member.workspace_id)
            .order_by(Connection.name)
        )
        return list(rows)

    async def count(self, member: Member) -> int:
        return (
            await self.session.scalar(
                select(func.count())
                .select_from(Connection)
                .where(Connection.workspace_id == member.workspace_id)
            )
            or 0
        )

    async def get(self, member: Member, connection_id: uuid.UUID) -> Connection | None:
        return await self.session.scalar(
            select(Connection).where(
                Connection.id == connection_id, Connection.workspace_id == member.workspace_id
            )
        )

    async def get_many(self, member: Member, ids: set[uuid.UUID]) -> list[Connection]:
        rows = await self.session.scalars(
            select(Connection).where(
                Connection.workspace_id == member.workspace_id, Connection.id.in_(ids)
            )
        )
        return list(rows)

    async def add(
        self, member: Member, type_id: str, name: str, config: dict[str, Any], encrypted: str
    ) -> Connection:
        connection = Connection(
            workspace_id=member.workspace_id,
            type=type_id,
            name=name,
            config=config,
            secrets_encrypted=encrypted,
            created_by=member.user_id,
            updated_by=member.user_id,
        )
        self.session.add(connection)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise NameTaken from None
        await self.session.refresh(connection)
        return connection

    async def replace(
        self,
        member: Member,
        connection_id: uuid.UUID,
        name: str,
        config: dict[str, Any],
        encrypted: str,
    ) -> Connection | None:
        statement = (
            update(Connection)
            .where(Connection.id == connection_id, Connection.workspace_id == member.workspace_id)
            .values(
                name=name,
                config=config,
                secrets_encrypted=encrypted,
                updated_by=member.user_id,
                updated_at=func.now(),
            )
            .returning(Connection)
            .execution_options(populate_existing=True)
        )
        try:
            connection = (await self.session.execute(statement)).scalar_one_or_none()
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise NameTaken from None
        return connection

    async def delete(self, member: Member, connection_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            delete(Connection)
            .where(Connection.id == connection_id, Connection.workspace_id == member.workspace_id)
            .returning(Connection.id)
        )
        await self.session.commit()
        return result.first() is not None

    async def flows_using(self, member: Member, connection_id: uuid.UUID) -> list[Flow]:
        """Live flows whose draft or latest published version has a node using the connection."""
        uses = {"nodes": [{"data": {"connection_id": str(connection_id)}}]}
        rows = await self.session.scalars(
            select(Flow)
            .outerjoin(
                FlowVersion,
                and_(
                    FlowVersion.flow_id == Flow.id,
                    FlowVersion.version == Flow.published_version,
                    FlowVersion.deleted_at.is_(None),
                ),
            )
            .where(
                Flow.workspace_id == member.workspace_id,
                Flow.deleted_at.is_(None),
                or_(Flow.draft.contains(uses), FlowVersion.graph.contains(uses)),
            )
            .order_by(Flow.name, Flow.id)
        )
        return list(rows)


def get_connection_store(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConnectionStore:
    return ConnectionStore(session)
