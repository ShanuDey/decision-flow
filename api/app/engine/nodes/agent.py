"""A model that decides which published flows to run, in a loop, until it can answer."""

import json
import uuid
from typing import Any, Literal

from pydantic import Field

from app.engine.base import StrictBaseModel
from app.engine.inputs import InputValidationError
from app.engine.issues import Issue
from app.engine.llm import (
    TOOL_NAME,
    AgentLimits,
    ToolSpec,
    input_schema,
    require_base_url,
    run_agent,
)
from app.engine.nodes.base import NodeContext, NodeModel
from app.engine.nodes.prompt import render_text

STOPPED = {
    "max_iterations": "the agent used all its steps without answering; raise max iterations",
    "max_tokens": "the agent used up its token budget without answering",
    "timeout": "the agent ran out of time without answering",
}


class AgentTool(StrictBaseModel):
    flow_id: str = ""
    # What the model sees: the flow's own name is not shown to it.
    name: str = ""
    description: str = ""


class AgentData(StrictBaseModel):
    connection_id: str = ""
    # Empty: the connection's default model.
    model: str = ""
    instructions: str = ""
    prompt: str = ""
    tools: list[AgentTool] = Field(default_factory=list)
    max_iterations: int = Field(default=8, ge=1, le=50)
    max_total_tokens: int | None = Field(default=None, ge=1)
    max_seconds: int | None = Field(default=None, ge=1)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1)
    timeout_seconds: int | None = Field(default=None, ge=1)


class AgentNode(NodeModel):
    type: Literal["agent"]
    data: AgentData = Field(default_factory=AgentData)

    def templates(self) -> dict[str, str]:
        d = self.data
        return {"data.model": d.model, "data.instructions": d.instructions, "data.prompt": d.prompt}

    def connection_ids(self) -> set[str]:
        return {self.data.connection_id} if self.data.connection_id else set()

    def called_flow_ids(self) -> list[str]:
        return [t.flow_id for t in self.data.tools if t.flow_id]

    def output_names(self, ctx: NodeContext) -> set[str] | None:
        return {"text", "steps", "iterations", "usage", "model"}

    def _issue(self, code: str, message: str, field: str) -> Issue:
        return Issue(code=code, message=message, node_id=self.id, field=field)

    def check(self, ctx: NodeContext) -> list[Issue]:
        d = self.data
        issues: list[Issue] = []
        if not d.connection_id:
            issues.append(
                self._issue("missing_connection", "pick a connection", "data.connection_id")
            )
        elif not _is_uuid(d.connection_id):
            issues.append(
                self._issue("invalid_connection", "pick a connection again", "data.connection_id")
            )
        if not d.prompt.strip():
            issues.append(
                self._issue("missing_prompt", "enter the task to give the agent", "data.prompt")
            )
        seen: set[str] = set()
        for i, tool in enumerate(d.tools):
            where = f"data.tools.{i}"
            if not _is_uuid(tool.flow_id):
                issues.append(self._issue("tool_not_selected", "pick a flow", f"{where}.flow_id"))
            elif ctx.contracts is not None and tool.flow_id not in ctx.contracts:
                issues.append(
                    self._issue(
                        "subflow_unavailable",
                        "the flow is missing, or has no published version",
                        f"{where}.flow_id",
                    )
                )
            if not TOOL_NAME.fullmatch(tool.name):
                issues.append(
                    self._issue(
                        "invalid_tool_name",
                        "name the tool with 1-64 letters, digits, '_' or '-'",
                        f"{where}.name",
                    )
                )
            elif tool.name in seen:
                issues.append(
                    self._issue(
                        "duplicate_tool_name", "another tool has this name", f"{where}.name"
                    )
                )
            seen.add(tool.name)
            if not tool.description.strip():
                issues.append(
                    self._issue(
                        "missing_tool_description",
                        "tell the model what the tool does and when to use it",
                        f"{where}.description",
                    )
                )
        return issues

    async def run(self, state: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        from app.engine.contracts import contract_of  # the nodes package imports this module

        d = self.data
        if ctx.outbound is None:
            raise ValueError("outbound requests are not configured")
        connection = ctx.secrets.connections.get(d.connection_id)
        if connection is None:
            raise ValueError("the connection is not available; pick it again in the node")
        require_base_url(connection)
        scopes = {
            "input": state.get("input", {}),
            "vars": state.get("vars", {}),
            "nodes": state.get("nodes", {}),
            "connection": connection.values,
        }
        model = render_text(d.model, scopes, "model").strip() or connection.values.get(
            "default_model", ""
        )
        if not model:
            raise ValueError("no model: set one in the node or a default model on the connection")
        runtime = ctx.subflows
        if d.tools and runtime is None:
            raise ValueError("flows are not available here")
        graphs: dict[str, Any] = {}
        specs: list[ToolSpec] = []
        for tool in d.tools:
            assert runtime is not None
            limit = runtime.access.max_depth
            if limit and runtime.depth >= limit:
                raise ValueError(f"flows are nested more than {limit} levels deep")
            graph = await runtime.access.load(tool.flow_id)
            graphs[tool.name] = graph
            schema = input_schema(contract_of(graph).inputs)
            specs.append(ToolSpec(name=tool.name, description=tool.description, parameters=schema))

        async def run_tool(name: str, arguments: dict[str, Any]) -> str:
            assert runtime is not None
            key = f"{runtime.scope}>{self.id}" if runtime.scope else self.id
            try:
                result = await runtime.execute(graphs[name], arguments, ctx, runtime, key)
            except InputValidationError as exc:
                raise ValueError(f"the flow rejected its input: {exc}") from None
            if result.status == "failed" or result.output is None:
                error = result.error
                where = f" at '{error.node_id}'" if error and error.node_id else ""
                raise ValueError(
                    f"the flow failed{where}: {error.message if error else 'no output'}"
                )
            return json.dumps(result.output)

        policy = ctx.outbound
        if d.timeout_seconds:
            policy = policy.model_copy(
                update={"timeout_seconds": min(d.timeout_seconds, policy.timeout_seconds)}
            )
        limits = {"max_iterations": d.max_iterations, "max_total_tokens": d.max_total_tokens}
        if d.max_seconds:
            limits["max_seconds"] = d.max_seconds
        result = await run_agent(
            policy,
            connection,
            model=model,
            instructions=render_text(d.instructions, scopes, "instructions"),
            messages=[{"role": "user", "content": render_text(d.prompt, scopes, "prompt")}],
            tools=specs,
            run_tool=run_tool,
            limits=AgentLimits(**limits),
            temperature=d.temperature,
            max_tokens=d.max_tokens,
        )
        if result.stop != "answer":
            raise ValueError(STOPPED[result.stop])
        output = {
            "text": result.text,
            "steps": [s.model_dump() for s in result.steps],
            "iterations": result.iterations,
            "usage": result.usage,
            "model": result.model,
        }
        return {"nodes": {self.id: {"output": output}}}


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True
