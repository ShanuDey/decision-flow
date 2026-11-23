"""The registry of node types. Adding a type: a new module here, then one line in each list."""

from typing import Annotated

from pydantic import Field

from app.engine.nodes.agent import AgentNode
from app.engine.nodes.assign import AssignNode
from app.engine.nodes.base import NodeContext, NodeModel
from app.engine.nodes.condition import ConditionNode
from app.engine.nodes.end import EndNode
from app.engine.nodes.http_request import HttpRequestNode
from app.engine.nodes.prompt import PromptNode
from app.engine.nodes.start import StartNode
from app.engine.nodes.structured_output import StructuredOutputNode
from app.engine.nodes.subflow import SubflowNode

NODE_TYPES: tuple[type[NodeModel], ...] = (
    StartNode,
    AssignNode,
    ConditionNode,
    HttpRequestNode,
    PromptNode,
    StructuredOutputNode,
    AgentNode,
    SubflowNode,
    EndNode,
)

# keep in step with NODE_TYPES (tested); this union parses the graph JSON
Node = Annotated[
    StartNode
    | AssignNode
    | ConditionNode
    | HttpRequestNode
    | PromptNode
    | StructuredOutputNode
    | AgentNode
    | SubflowNode
    | EndNode,
    Field(discriminator="type"),
]

__all__ = [
    "NODE_TYPES",
    "AgentNode",
    "AssignNode",
    "ConditionNode",
    "EndNode",
    "HttpRequestNode",
    "Node",
    "NodeContext",
    "NodeModel",
    "PromptNode",
    "StartNode",
    "StructuredOutputNode",
    "SubflowNode",
]
