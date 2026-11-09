from typing import Any, ClassVar, Self, get_args

from pydantic import Field

from app.engine.base import FrozenBaseModel, StrictBaseModel
from app.engine.fields import Variable
from app.engine.issues import Issue


class Position(StrictBaseModel):
    x: float = 0
    y: float = 0


class NodeContext(FrozenBaseModel):
    variables: list[Variable]


class NodeModel(StrictBaseModel):
    """Base of every node type. A subclass adds `type`, `data`, `run`, and overrides the traits."""

    id: str
    name: str | None = None  # defaults to the type; unique per flow
    position: Position = Field(default_factory=Position)

    # How many of this type a flow may have, and whether edges may enter or leave it.
    min_count: ClassVar[int] = 0
    max_count: ClassVar[int | None] = None
    accepts_incoming: ClassVar[bool] = True
    accepts_outgoing: ClassVar[bool] = True

    @classmethod
    def type_name(cls) -> str:
        return get_args(cls.model_fields["type"].annotation)[0]

    async def run(self, state: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        """Return the state update. Raising fails the run, tagged with this node's id."""
        raise NotImplementedError

    def templates(self) -> dict[str, str]:
        """Template settings by field path, so the validator can check what they reference."""
        return {}

    @classmethod
    def check_group(cls, nodes: list[Self]) -> list[Issue]:
        return []
