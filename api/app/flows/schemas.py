import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.engine.base import FrozenBaseModel


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
