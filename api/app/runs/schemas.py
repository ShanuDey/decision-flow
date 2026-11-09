import uuid
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
