"""An in-memory AgentStore, so router tests need no database."""

import uuid
from datetime import UTC, datetime
from typing import Any

from app.agents.models import Agent, AgentMessage, AgentThread
from app.agents.store import NameTaken, NewMessage
from app.workspaces.schemas import Member


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class FakeAgentStore:
    def __init__(self) -> None:
        self.agents: dict[uuid.UUID, Agent] = {}
        self.threads: dict[uuid.UUID, AgentThread] = {}
        self.messages: dict[uuid.UUID, list[AgentMessage]] = {}

    def _mine(self, member: Member) -> list[Agent]:
        return [a for a in self.agents.values() if a.workspace_id == member.workspace_id]

    def _taken(self, member: Member, name: str, keep: uuid.UUID | None = None) -> bool:
        return any(a.name == name and a.id != keep for a in self._mine(member))

    async def list_agents(self, member: Member) -> list[Agent]:
        return sorted(self._mine(member), key=lambda a: a.name)

    async def count(self, member: Member) -> int:
        return len(self._mine(member))

    async def get(self, member: Member, agent_id: uuid.UUID) -> Agent | None:
        agent = self.agents.get(agent_id)
        return agent if agent and agent.workspace_id == member.workspace_id else None

    async def add(self, member: Member, name: str, fields: dict[str, Any]) -> Agent:
        if self._taken(member, name):
            raise NameTaken
        agent = Agent(
            id=uuid.uuid4(),
            workspace_id=member.workspace_id,
            name=name,
            created_by=member.user_id,
            updated_by=member.user_id,
            created_at=now(),
            updated_at=now(),
            **fields,
        )
        self.agents[agent.id] = agent
        return agent

    async def replace(
        self, member: Member, agent_id: uuid.UUID, name: str, fields: dict[str, Any]
    ) -> Agent | None:
        agent = await self.get(member, agent_id)
        if agent is None:
            return None
        if self._taken(member, name, keep=agent_id):
            raise NameTaken
        agent.name = name
        for key, value in fields.items():
            setattr(agent, key, value)
        agent.updated_at = now()
        return agent

    async def delete(self, member: Member, agent_id: uuid.UUID) -> bool:
        if await self.get(member, agent_id) is None:
            return False
        del self.agents[agent_id]
        for thread in [t for t in self.threads.values() if t.agent_id == agent_id]:
            del self.threads[thread.id]
            self.messages.pop(thread.id, None)
        return True

    async def agents_using(self, member: Member, connection_id: uuid.UUID) -> list[Agent]:
        return [a for a in await self.list_agents(member) if a.connection_id == connection_id]

    async def create_thread(self, member: Member, agent_id: uuid.UUID) -> AgentThread:
        thread = AgentThread(
            id=uuid.uuid4(),
            agent_id=agent_id,
            workspace_id=member.workspace_id,
            created_by=member.user_id,
            title="",
            created_at=now(),
            updated_at=now(),
        )
        self.threads[thread.id] = thread
        self.messages[thread.id] = []
        return thread

    async def list_threads(
        self, member: Member, agent_id: uuid.UUID, limit: int
    ) -> list[AgentThread]:
        mine = [
            t
            for t in self.threads.values()
            if t.agent_id == agent_id
            and t.workspace_id == member.workspace_id
            and t.created_by == member.user_id
        ]
        return sorted(mine, key=lambda t: t.updated_at, reverse=True)[:limit]

    async def get_thread(
        self, member: Member, agent_id: uuid.UUID, thread_id: uuid.UUID
    ) -> AgentThread | None:
        thread = self.threads.get(thread_id)
        if (
            thread
            and thread.agent_id == agent_id
            and thread.workspace_id == member.workspace_id
            and thread.created_by == member.user_id
        ):
            return thread
        return None

    async def delete_thread(
        self, member: Member, agent_id: uuid.UUID, thread_id: uuid.UUID
    ) -> bool:
        if await self.get_thread(member, agent_id, thread_id) is None:
            return False
        del self.threads[thread_id]
        self.messages.pop(thread_id, None)
        return True

    async def list_messages(self, thread_id: uuid.UUID) -> list[AgentMessage]:
        return list(self.messages.get(thread_id, []))

    async def get_message(self, thread_id: uuid.UUID, message_id: uuid.UUID) -> AgentMessage | None:
        return next((m for m in self.messages.get(thread_id, []) if m.id == message_id), None)

    async def add_messages(
        self, thread: AgentThread, new: list[NewMessage], title: str
    ) -> list[AgentMessage]:
        rows = self.messages[thread.id]
        added = [
            AgentMessage(
                id=uuid.uuid4(),
                thread_id=thread.id,
                seq=len(rows) + i + 1,
                role=m.role,
                content=m.content,
                steps=m.steps,
                usage=m.usage,
                model=m.model,
                trace_id=m.trace_id,
                created_at=now(),
            )
            for i, m in enumerate(new)
        ]
        rows.extend(added)
        thread.title = thread.title or title
        thread.updated_at = now()
        return added
