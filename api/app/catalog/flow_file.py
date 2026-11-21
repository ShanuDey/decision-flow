"""What a marketplace flow is: a graph plus the connections its request nodes stand in for."""

import re
import uuid
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from app.engine.base import FrozenBaseModel
from app.engine.nodes import HttpRequestNode
from app.engine.validate import parse_graph

FLOW_ID = re.compile(r"[a-z][a-z0-9_]{0,63}")


class FlowConnection(FrozenBaseModel):
    type: str
    # Shown when the user matches this slot to one of their own connections.
    name: str


class CatalogFlow(FrozenBaseModel):
    schema_version: Literal[1] = 1
    version: str = Field("1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    id: str
    name: str
    description: str
    icon: str = "workflow"
    tags: list[str] = Field(default_factory=list)
    # Keyed by the placeholder id the draft's request nodes carry as `connection_id`.
    connections: dict[str, FlowConnection] = Field(default_factory=dict)
    draft: dict[str, Any]

    @model_validator(mode="after")
    def _check(self) -> Self:
        """A file is data, so it must be a valid flow that only uses what it declares."""
        problems: list[str] = []
        if not FLOW_ID.fullmatch(self.id):
            problems.append("id must be lowercase letters, digits and underscores")
        if bad := next((key for key in self.connections if not _is_uuid(key)), None):
            problems.append(f"connection key '{bad}' must be a UUID")
        graph, issues = parse_graph(self.draft)
        problems += [issue.message for issue in issues]
        if graph is not None:
            if any(node.type == "subflow" for node in graph.nodes):
                problems.append("a subflow node needs a flow of the installer's workspace")
            used = {n.data.connection_id for n in graph.nodes if isinstance(n, HttpRequestNode)}
            used.discard("")
            if undeclared := sorted(used - set(self.connections)):
                problems.append(f"connection {undeclared[0]} is used but not declared")
            if unused := sorted(set(self.connections) - used):
                problems.append(f"connection {unused[0]} is declared but no node uses it")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def input_names(self) -> list[str]:
        return _names(self.draft, "start", "inputs")

    def output_names(self) -> list[str]:
        return _names(self.draft, "end", "outputs")


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def _names(draft: dict[str, Any], node_type: str, key: str) -> list[str]:
    return [
        item["name"]
        for node in draft.get("nodes", [])
        if node.get("type") == node_type
        for item in node.get("data", {}).get(key, [])
    ]
