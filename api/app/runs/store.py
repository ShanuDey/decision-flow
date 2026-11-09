import uuid
from typing import Annotated

from fastapi import Depends
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

    async def get_run(self, run_id: uuid.UUID) -> Run | None:
        return await self.session.get(Run, run_id)


def get_run_store(session: Annotated[AsyncSession, Depends(get_session)]) -> RunStore:
    return RunStore(session)
