"""Published flows offered to a model as tools; shared by the Agent node and the agent resource."""

import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from app.engine.base import StrictBaseModel
from app.engine.inputs import InputValidationError
from app.engine.llm import TOOL_NAME, ToolSpec, input_schema

Loader = Callable[[str], Awaitable[Any]]
# Runs a loaded graph with the model's arguments and returns the engine's RunResult.
Executor = Callable[[Any, dict[str, Any]], Awaitable[Any]]


class AgentTool(StrictBaseModel):
    flow_id: str = ""
    # What the model sees: the flow's own name is not shown to it.
    name: str = ""
    description: str = ""


def check_tools(tools: list[AgentTool]) -> str | None:
    """The first problem with a list of tools, or None."""
    seen: set[str] = set()
    for i, tool in enumerate(tools, 1):
        try:
            uuid.UUID(tool.flow_id)
        except ValueError:
            return f"tool {i}: pick a flow"
        if not TOOL_NAME.fullmatch(tool.name):
            return f"tool {i}: the name must be 1-64 letters, digits, _ or -"
        if tool.name in seen:
            return f"tool {i}: another tool is named {tool.name}"
        seen.add(tool.name)
        if not tool.description.strip():
            return f"tool {tool.name}: say what it does and when to use it"
    return None


class FlowTools:
    def __init__(self, specs: list[ToolSpec], graphs: dict[str, Any]) -> None:
        self.specs = specs
        self._graphs = graphs

    @classmethod
    async def load(cls, tools: list[AgentTool], load: Loader) -> "FlowTools":
        """Raises ValueError when a flow cannot be loaded."""
        from app.engine.contracts import contract_of  # the nodes package imports this module

        graphs: dict[str, Any] = {}
        specs: list[ToolSpec] = []
        for tool in tools:
            graph = await load(tool.flow_id)
            graphs[tool.name] = graph
            schema = input_schema(contract_of(graph).inputs)
            specs.append(ToolSpec(name=tool.name, description=tool.description, parameters=schema))
        return cls(specs, graphs)

    async def run(self, name: str, arguments: dict[str, Any], execute: Executor) -> str:
        """The flow's outputs as JSON text; ValueError says why it failed, for the model to read."""
        try:
            result = await execute(self._graphs[name], arguments)
        except InputValidationError as exc:
            raise ValueError(f"the flow rejected its input: {exc}") from None
        if result.status == "failed" or result.output is None:
            error = result.error
            where = f" at '{error.node_id}'" if error and error.node_id else ""
            raise ValueError(f"the flow failed{where}: {error.message if error else 'no output'}")
        return json.dumps(result.output)
