from typing import Literal

from pydantic import Field

from app.engine.base import StrictBaseModel
from app.engine.fields import Variable
from app.engine.nodes import Node


class Edge(StrictBaseModel):
    id: str
    source: str
    target: str
    sourceHandle: str | None = None


class Graph(StrictBaseModel):
    schema_version: Literal[1]
    variables: list[Variable] = Field(default_factory=list)
    nodes: list[Node]
    edges: list[Edge] = Field(default_factory=list)
