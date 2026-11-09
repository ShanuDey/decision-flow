import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.engine.base import FrozenBaseModel
from app.engine.runtime import RunError


class FlowCreate(FrozenBaseModel):
    name: str = Field(min_length=1, max_length=120)
    # Omitted: a blank Start -> End graph.
    draft: dict[str, Any] | None = None


class FlowSummary(FrozenBaseModel):
    id: uuid.UUID
    name: str
    draft_version: int
    created_at: datetime
    updated_at: datetime


class FlowDetail(FlowSummary):
    draft: dict[str, Any]


class FlowList(FrozenBaseModel):
    items: list[FlowSummary]
    total: int
    page: int
    page_size: int


class DraftSaved(FrozenBaseModel):
    draft_version: int


class ValidateResponse(FrozenBaseModel):
    valid: Literal[True]


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
