import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.engine.base import FrozenBaseModel
from app.engine.runtime import RunError


class RunRequest(FrozenBaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    # Until publish exists only the draft can run.
    test: bool = False


class RunResponse(FrozenBaseModel):
    run_id: uuid.UUID
    status: Literal["succeeded", "failed"]
    output: dict[str, Any] | None
    error: RunError | None
    duration_ms: int


class RunSummary(FrozenBaseModel):
    run_id: uuid.UUID
    flow_id: uuid.UUID
    status: Literal["succeeded", "failed"]
    test: bool
    error: RunError | None
    duration_ms: int
    started_at: datetime


class RunList(FrozenBaseModel):
    items: list[RunSummary]
    next_cursor: str | None
