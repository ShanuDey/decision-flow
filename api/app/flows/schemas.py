import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import StringConstraints

from app.engine.base import FrozenBaseModel

FlowName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class FlowCreate(FrozenBaseModel):
    name: FlowName
    # Omitted: a blank Start -> End graph.
    draft: dict[str, Any] | None = None


class FlowRename(FrozenBaseModel):
    name: FlowName


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
