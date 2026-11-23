import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(500), default="")
    # Cleared when the connection is deleted; a turn then fails until another is picked.
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("connections.id", ondelete="SET NULL"), index=True
    )
    model: Mapped[str] = mapped_column(String(200), default="")
    instructions: Mapped[str] = mapped_column(Text, default="")
    tools: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    # max_iterations, max_total_tokens, max_seconds, temperature, max_tokens, timeout_seconds
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AgentThread(Base):
    __tablename__ = "agent_threads"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AgentMessage(Base):
    __tablename__ = "agent_messages"
    __table_args__ = (UniqueConstraint("thread_id", "seq"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_threads.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int]
    # "user" or "assistant"; the tool calls of a turn are kept on the assistant message.
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    steps: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    usage: Mapped[dict[str, int] | None] = mapped_column(JSONB)
    model: Mapped[str | None] = mapped_column(String(200))
    # The MLflow trace of the turn, on the assistant message; null if it was not recorded.
    trace_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
