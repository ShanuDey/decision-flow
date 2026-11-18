"""What a flow shows other flows, and what a run needs to start a flow from inside another."""

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import Field

from app.engine.base import FrozenBaseModel
from app.engine.fields import FieldDef, TypedField


class FlowContract(FrozenBaseModel):
    """A published flow as its callers see it, plus what following the call chain needs."""

    inputs: list[FieldDef] = Field(default_factory=list)
    outputs: list[TypedField] = Field(default_factory=list)
    calls: list[str] = Field(default_factory=list)
    secret_names: list[str] = Field(default_factory=list)
    connection_ids: list[str] = Field(default_factory=list)


class SubflowAccess(FrozenBaseModel):
    # Returns the latest published graph of a flow in the caller's workspace, or raises ValueError.
    load: Callable[[str], Awaitable[Any]]
    max_depth: int = 0


class SubflowRuntime(FrozenBaseModel):
    access: SubflowAccess
    # Set by the runtime, which alone may compile and run a graph.
    execute: Callable[..., Awaitable[Any]]
    depth: int = 0
    scope: str = ""
