import uuid
from datetime import datetime
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.runs.models import Run
from app.workspaces.schemas import Member


class FlowGone(Exception):
    """The run's flow was deleted while the run was in flight."""


class RunStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_run(self, run: Run) -> Run:
        self.session.add(run)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise FlowGone from exc
        await self.session.refresh(run)
        return run

    async def list_runs(
        self,
        member: Member,
        flow_id: uuid.UUID | None,
        status: str | None,
        test: bool | None,
        started_from: datetime | None,
        started_to: datetime | None,
        after: tuple[datetime, uuid.UUID] | None,
        limit: int,
    ) -> list[Run]:
        """Newest first, at most `limit` rows."""
        query = select(Run).where(Run.workspace_id == member.workspace_id)
        for column, value in ((Run.flow_id, flow_id), (Run.status, status), (Run.test, test)):
            if value is not None:
                query = query.where(column == value)
        if started_from is not None:
            query = query.where(Run.started_at >= started_from)
        if started_to is not None:
            query = query.where(Run.started_at <= started_to)
        if after is not None:
            query = query.where(tuple_(Run.started_at, Run.id) < tuple_(*after))
        rows = await self.session.scalars(
            query.order_by(Run.started_at.desc(), Run.id.desc()).limit(limit)
        )
        return list(rows)

    async def get_run(self, member: Member, run_id: uuid.UUID) -> Run | None:
        return await self.session.scalar(
            select(Run).where(Run.id == run_id, Run.workspace_id == member.workspace_id)
        )


def get_run_store(session: Annotated[AsyncSession, Depends(get_session)]) -> RunStore:
    return RunStore(session)
