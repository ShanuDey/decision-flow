"""Persistence for agents, threads and messages. Tests swap this class for an in-memory fake."""

import uuid
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.models import Agent, AgentMessage, AgentThread
from app.db import get_session
from app.workspaces.schemas import Member


class NameTaken(Exception):
    pass


class ThreadBusy(Exception):
    pass


class NewMessage:
    """A message to append; the store assigns its position."""

    def __init__(
        self,
        role: str,
        content: str,
        steps: list[dict[str, Any]] | None = None,
        usage: dict[str, int] | None = None,
        model: str | None = None,
    ) -> None:
        self.role, self.content, self.steps, self.usage, self.model = (
            role,
            content,
            steps,
            usage,
            model,
        )


class AgentStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_agents(self, member: Member) -> list[Agent]:
        rows = await self.session.scalars(
            select(Agent).where(Agent.workspace_id == member.workspace_id).order_by(Agent.name)
        )
        return list(rows)

    async def count(self, member: Member) -> int:
        return (
            await self.session.scalar(
                select(func.count())
                .select_from(Agent)
                .where(Agent.workspace_id == member.workspace_id)
            )
            or 0
        )

    async def get(self, member: Member, agent_id: uuid.UUID) -> Agent | None:
        return await self.session.scalar(
            select(Agent).where(Agent.id == agent_id, Agent.workspace_id == member.workspace_id)
        )

    async def add(self, member: Member, name: str, fields: dict[str, Any]) -> Agent:
        agent = Agent(
            workspace_id=member.workspace_id,
            name=name,
            created_by=member.user_id,
            updated_by=member.user_id,
            **fields,
        )
        self.session.add(agent)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise NameTaken from None
        await self.session.refresh(agent)
        return agent

    async def replace(
        self, member: Member, agent_id: uuid.UUID, name: str, fields: dict[str, Any]
    ) -> Agent | None:
        statement = (
            update(Agent)
            .where(Agent.id == agent_id, Agent.workspace_id == member.workspace_id)
            .values(name=name, **fields, updated_by=member.user_id, updated_at=func.now())
            .returning(Agent)
            .execution_options(populate_existing=True)
        )
        try:
            agent = (await self.session.execute(statement)).scalar_one_or_none()
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise NameTaken from None
        return agent

    async def delete(self, member: Member, agent_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            delete(Agent)
            .where(Agent.id == agent_id, Agent.workspace_id == member.workspace_id)
            .returning(Agent.id)
        )
        await self.session.commit()
        return result.first() is not None

    async def agents_using(self, member: Member, connection_id: uuid.UUID) -> list[Agent]:
        rows = await self.session.scalars(
            select(Agent)
            .where(Agent.workspace_id == member.workspace_id, Agent.connection_id == connection_id)
            .order_by(Agent.name)
        )
        return list(rows)

    async def create_thread(self, member: Member, agent_id: uuid.UUID) -> AgentThread:
        thread = AgentThread(
            agent_id=agent_id, workspace_id=member.workspace_id, created_by=member.user_id
        )
        self.session.add(thread)
        await self.session.commit()
        await self.session.refresh(thread)
        return thread

    async def list_threads(
        self, member: Member, agent_id: uuid.UUID, limit: int
    ) -> list[AgentThread]:
        rows = await self.session.scalars(
            select(AgentThread)
            .where(
                AgentThread.agent_id == agent_id,
                AgentThread.workspace_id == member.workspace_id,
                AgentThread.created_by == member.user_id,
            )
            .order_by(AgentThread.updated_at.desc(), AgentThread.id)
            .limit(limit)
        )
        return list(rows)

    async def get_thread(
        self, member: Member, agent_id: uuid.UUID, thread_id: uuid.UUID
    ) -> AgentThread | None:
        return await self.session.scalar(
            select(AgentThread).where(
                AgentThread.id == thread_id,
                AgentThread.agent_id == agent_id,
                AgentThread.workspace_id == member.workspace_id,
                AgentThread.created_by == member.user_id,
            )
        )

    async def delete_thread(
        self, member: Member, agent_id: uuid.UUID, thread_id: uuid.UUID
    ) -> bool:
        result = await self.session.execute(
            delete(AgentThread)
            .where(
                AgentThread.id == thread_id,
                AgentThread.agent_id == agent_id,
                AgentThread.workspace_id == member.workspace_id,
                AgentThread.created_by == member.user_id,
            )
            .returning(AgentThread.id)
        )
        await self.session.commit()
        return result.first() is not None

    async def list_messages(self, thread_id: uuid.UUID) -> list[AgentMessage]:
        rows = await self.session.scalars(
            select(AgentMessage)
            .where(AgentMessage.thread_id == thread_id)
            .order_by(AgentMessage.seq)
        )
        return list(rows)

    async def add_messages(
        self, thread: AgentThread, new: list[NewMessage], title: str
    ) -> list[AgentMessage]:
        """Appends in order and bumps the thread; the title is set only if it has none."""
        last = await self.session.scalar(
            select(func.max(AgentMessage.seq)).where(AgentMessage.thread_id == thread.id)
        )
        rows = [
            AgentMessage(
                thread_id=thread.id,
                seq=(last or 0) + i + 1,
                role=m.role,
                content=m.content,
                steps=m.steps,
                usage=m.usage,
                model=m.model,
            )
            for i, m in enumerate(new)
        ]
        self.session.add_all(rows)
        try:
            await self.session.execute(
                update(AgentThread)
                .where(AgentThread.id == thread.id)
                .values(updated_at=func.now(), title=thread.title or title)
            )
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise ThreadBusy from None
        for row in rows:
            await self.session.refresh(row)
        return rows


def get_agent_store(session: Annotated[AsyncSession, Depends(get_session)]) -> AgentStore:
    return AgentStore(session)
