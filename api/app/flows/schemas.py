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
    published_version: int | None
    published_draft_version: int | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FlowDetail(FlowSummary):
    draft: dict[str, Any]


class VersionSummary(FrozenBaseModel):
    version: int
    source_draft_version: int
    created_at: datetime


class VersionDetail(VersionSummary):
    graph: dict[str, Any]


class VersionList(FrozenBaseModel):
    items: list[VersionSummary]
    # How many newest versions are kept; 0 keeps all.
    keep_latest: int


class FlowList(FrozenBaseModel):
    items: list[FlowSummary]
    total: int
    page: int
    page_size: int


class FlowFormatExample(FrozenBaseModel):
    id: str
    title: str
    summary: str
    draft: dict[str, Any]


class FlowFormat(FrozenBaseModel):
    guide: str
    node_types: list[str]
    graph_schema: dict[str, Any]
    examples: list[FlowFormatExample]


class DraftSaved(FrozenBaseModel):
    draft_version: int


class ValidateResponse(FrozenBaseModel):
    valid: Literal[True]


class EvaluateRequest(FrozenBaseModel):
    kind: Literal["expression", "template"] = "expression"
    source: Annotated[str, StringConstraints(max_length=2000)]
    # Omitted: only check that the source is well formed.
    scope: dict[str, Any] | None = None


class EvaluateResponse(FrozenBaseModel):
    valid: bool
    return_type: str | None = None
    result: Any = None
    error: str | None = None
