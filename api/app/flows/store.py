"""Persistence for flows and runs. Tests swap this class for an in-memory fake."""

import uuid
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.flows.models import Flow, Run

SORTABLE = {"name": Flow.name, "created_at": Flow.created_at, "updated_at": Flow.updated_at}


class FlowStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_flow(self, name: str, draft: dict[str, Any]) -> Flow:
        flow = Flow(name=name, draft=draft)
        self.session.add(flow)
        await self.session.commit()
        await self.session.refresh(flow)
        return flow

    async def list_flows(
        self, q: str | None, sort: str, page: int, page_size: int
    ) -> tuple[list[Flow], int]:
        column = SORTABLE[sort.lstrip("-")]
        query = select(Flow)
        if q:
            query = query.where(Flow.name.ilike(f"%{q}%"))
        total = await self.session.scalar(select(func.count()).select_from(query.subquery()))
        order = column.desc() if sort.startswith("-") else column.asc()
        rows = await self.session.scalars(
            query.order_by(order, Flow.id).offset((page - 1) * page_size).limit(page_size)
        )
        return list(rows), total or 0

    async def get_flow(self, flow_id: uuid.UUID) -> Flow | None:
        return await self.session.get(Flow, flow_id)

    async def save_draft(
        self, flow_id: uuid.UUID, draft: dict[str, Any], expected_version: int
    ) -> Flow | None:
        """None when the version is stale (or the flow is gone): the caller tells them apart."""
        result = await self.session.execute(
            update(Flow)
            .where(Flow.id == flow_id, Flow.draft_version == expected_version)
            .values(draft=draft, draft_version=Flow.draft_version + 1, updated_at=func.now())
            .returning(Flow)
            .execution_options(populate_existing=True)
        )
        flow = result.scalar_one_or_none()
        await self.session.commit()
        return flow

    async def add_run(self, run: Run) -> Run:
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def get_run(self, run_id: uuid.UUID) -> Run | None:
        return await self.session.get(Run, run_id)


def get_store(session: Annotated[AsyncSession, Depends(get_session)]) -> FlowStore:
    return FlowStore(session)
