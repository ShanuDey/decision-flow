import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.engine.base import FrozenBaseModel
from app.engine.runtime import RunError


class RunRequest(FrozenBaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    # true runs the draft; false runs the latest published version.
    test: bool = False


class RunResponse(FrozenBaseModel):
    run_id: uuid.UUID
    status: Literal["succeeded", "failed"]
    flow_version: int | None
    output: dict[str, Any] | None
    error: RunError | None
    duration_ms: int


class RunSummary(FrozenBaseModel):
    run_id: uuid.UUID
    flow_id: uuid.UUID
    flow_name: str
    # The flow was deleted but kept (DELETE_MODE=soft); its runs stay listed.
    flow_deleted: bool
    status: Literal["succeeded", "failed"]
    test: bool
    flow_version: int | None
    error: RunError | None
    duration_ms: int
    started_at: datetime


class RunList(FrozenBaseModel):
    items: list[RunSummary]
    next_cursor: str | None


class RunDetail(RunSummary):
    input: dict[str, Any]
    output: dict[str, Any] | None


class RunStep(FrozenBaseModel):
    id: str
    parent_id: str | None
    kind: Literal["node", "llm", "tool", "parser", "other"]
    node_id: str | None
    node_type: str | None
    name: str
    status: Literal["ok", "failed"]
    error: str | None
    start_offset_ms: float
    duration_ms: float
    input: Any
    output: Any


class RunSteps(FrozenBaseModel):
    items: list[RunStep]
    # The trace is exported a moment after the run ends.
    pending: bool
