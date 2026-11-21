import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.engine.agent_tools import AgentTool
from app.engine.base import FrozenBaseModel
from app.engine.llm import MAX_TOOLS

AgentName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
MAX_MESSAGE_CHARS = 20_000


class AgentSettings(FrozenBaseModel):
    """What an agent is; the same fields are sent to create it and returned when it is read."""

    description: str = Field(default="", max_length=500)
    connection_id: uuid.UUID | None = None
    # Empty: the connection's default model.
    model: str = Field(default="", max_length=200)
    instructions: str = Field(default="", max_length=20_000)
    tools: list[AgentTool] = Field(default_factory=list, max_length=MAX_TOOLS)
    max_iterations: int = Field(default=8, ge=1, le=50)
    max_total_tokens: int | None = Field(default=None, ge=1)
    max_seconds: int | None = Field(default=None, ge=1)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1)
    timeout_seconds: int | None = Field(default=None, ge=1)


class AgentCreate(AgentSettings):
    name: AgentName


class AgentUpdate(FrozenBaseModel):
    """Only the fields you send change; send null to clear an optional one."""

    name: AgentName | None = None
    description: str | None = Field(default=None, max_length=500)
    connection_id: uuid.UUID | None = None
    model: str | None = Field(default=None, max_length=200)
    instructions: str | None = Field(default=None, max_length=20_000)
    tools: list[AgentTool] | None = Field(default=None, max_length=MAX_TOOLS)
    max_iterations: int | None = Field(default=None, ge=1, le=50)
    max_total_tokens: int | None = Field(default=None, ge=1)
    max_seconds: int | None = Field(default=None, ge=1)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1)
    timeout_seconds: int | None = Field(default=None, ge=1)


class AgentSummary(AgentSettings):
    id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime


class AgentList(FrozenBaseModel):
    items: list[AgentSummary]


class ThreadSummary(FrozenBaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ThreadList(FrozenBaseModel):
    items: list[ThreadSummary]


class ToolCallInfo(FrozenBaseModel):
    name: str
    arguments: dict[str, object]
    result: str
    is_error: bool


class MessageInfo(FrozenBaseModel):
    id: uuid.UUID
    seq: int
    role: Literal["user", "assistant"]
    content: str
    # The flows the agent ran to answer; only on assistant messages.
    steps: list[ToolCallInfo] | None
    usage: dict[str, int] | None
    model: str | None
    # Whether a trace of how the agent answered can be read.
    traced: bool
    created_at: datetime


class ThreadDetail(FrozenBaseModel):
    thread: ThreadSummary
    messages: list[MessageInfo]


class MessageRequest(FrozenBaseModel):
    content: Annotated[str, StringConstraints(min_length=1, max_length=MAX_MESSAGE_CHARS)]


class TurnResponse(FrozenBaseModel):
    user_message: MessageInfo
    reply: MessageInfo
