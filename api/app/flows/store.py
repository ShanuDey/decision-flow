"""Persistence for flows and runs. Tests swap this class for an in-memory fake."""

import uuid
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.flows.models import Flow
from app.workspaces.schemas import Member

SORTABLE = {"name": Flow.name, "created_at": Flow.created_at, "updated_at": Flow.updated_at}


class FlowStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_flow(self, member: Member, name: str, draft: dict[str, Any]) -> Flow:
        flow = Flow(
            workspace_id=member.workspace_id,
            created_by=member.user_id,
            updated_by=member.user_id,
            name=name,
            draft=draft,
        )
        self.session.add(flow)
        await self.session.commit()
        await self.session.refresh(flow)
        return flow

    async def count_flows(self, member: Member) -> int:
        return (
            await self.session.scalar(
                select(func.count())
                .select_from(Flow)
                .where(Flow.workspace_id == member.workspace_id, Flow.created_by == member.user_id)
            )
            or 0
        )

    async def list_flows(
        self, member: Member, q: str | None, sort: str, page: int, page_size: int
    ) -> tuple[list[Flow], int]:
        column = SORTABLE[sort.lstrip("-")]
        query = select(Flow).where(Flow.workspace_id == member.workspace_id)
        if q:
            query = query.where(Flow.name.icontains(q, autoescape=True))  # % and _ stay literal
        total = await self.session.scalar(select(func.count()).select_from(query.subquery()))
        order = column.desc() if sort.startswith("-") else column.asc()
        rows = await self.session.scalars(
            query.order_by(order, Flow.id).offset((page - 1) * page_size).limit(page_size)
        )
        return list(rows), total or 0

    async def get_flow(self, member: Member, flow_id: uuid.UUID) -> Flow | None:
        return await self.session.scalar(
            select(Flow).where(Flow.id == flow_id, Flow.workspace_id == member.workspace_id)
        )

    async def rename_flow(self, member: Member, flow_id: uuid.UUID, name: str) -> Flow | None:
        result = await self.session.execute(
            update(Flow)
            .where(Flow.id == flow_id, Flow.workspace_id == member.workspace_id)
            .values(name=name, updated_by=member.user_id, updated_at=func.now())
            .returning(Flow)
            .execution_options(populate_existing=True)
        )
        flow = result.scalar_one_or_none()
        await self.session.commit()
        return flow

    async def delete_flow(self, member: Member, flow_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            delete(Flow)
            .where(Flow.id == flow_id, Flow.workspace_id == member.workspace_id)
            .returning(Flow.id)
        )
        deleted = result.scalar_one_or_none()
        await self.session.commit()
        return deleted is not None

    async def save_draft(
        self, member: Member, flow_id: uuid.UUID, draft: dict[str, Any], expected_version: int
    ) -> Flow | None:
        """None when the version is stale (or the flow is gone): the caller tells them apart."""
        result = await self.session.execute(
            update(Flow)
            .where(
                Flow.id == flow_id,
                Flow.workspace_id == member.workspace_id,
                Flow.draft_version == expected_version,
            )
            .values(
                draft=draft,
                draft_version=Flow.draft_version + 1,
                updated_by=member.user_id,
                updated_at=func.now(),
            )
            .returning(Flow)
            .execution_options(populate_existing=True)
        )
        flow = result.scalar_one_or_none()
        await self.session.commit()
        return flow


def get_store(session: Annotated[AsyncSession, Depends(get_session)]) -> FlowStore:
    return FlowStore(session)
