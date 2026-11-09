"""The registry of node types. Adding a type: a new module here, then one line in each list."""

from typing import Annotated

from pydantic import Field

from app.engine.nodes.base import NodeContext, NodeModel
from app.engine.nodes.end import EndNode
from app.engine.nodes.start import StartNode

NODE_TYPES: tuple[type[NodeModel], ...] = (StartNode, EndNode)

# Keep in step with NODE_TYPES (a test checks it): the union is what parses the graph JSON.
Node = Annotated[StartNode | EndNode, Field(discriminator="type")]

__all__ = ["NODE_TYPES", "EndNode", "Node", "NodeContext", "NodeModel", "StartNode"]
