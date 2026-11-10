import uuid
from datetime import datetime
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.runs.models import Run


class RunStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_run(self, run: Run) -> Run:
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def list_runs(
        self,
        flow_id: uuid.UUID | None,
        status: str | None,
        test: bool | None,
        started_from: datetime | None,
        started_to: datetime | None,
        after: tuple[datetime, uuid.UUID] | None,
        limit: int,
    ) -> list[Run]:
        """Newest first, at most `limit` rows."""
        query = select(Run)
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

    async def get_run(self, run_id: uuid.UUID) -> Run | None:
        return await self.session.get(Run, run_id)


def get_run_store(session: Annotated[AsyncSession, Depends(get_session)]) -> RunStore:
    return RunStore(session)
