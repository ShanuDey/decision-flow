"""Runs another published flow as one step and returns its outputs."""

import uuid
from typing import Any, Literal

from pydantic import Field

from app.engine.base import StrictBaseModel
from app.engine.inputs import InputValidationError
from app.engine.issues import Issue
from app.engine.nodes.base import NodeContext, NodeModel
from app.engine.templates import TemplateError, render


class SubflowData(StrictBaseModel):
    flow_id: str = ""
    inputs: dict[str, str] = Field(default_factory=dict)  # child input name -> template


class SubflowNode(NodeModel):
    type: Literal["subflow"]
    data: SubflowData = Field(default_factory=SubflowData)

    def templates(self) -> dict[str, str]:
        return {f"data.inputs.{name}": value for name, value in self.data.inputs.items()}

    def called_flow_ids(self) -> list[str]:
        return [self.data.flow_id] if self.data.flow_id else []

    def _issue(self, code: str, message: str, field: str) -> Issue:
        return Issue(code=code, message=message, node_id=self.id, field=field)

    def check(self, ctx: NodeContext) -> list[Issue]:
        flow_id = self.data.flow_id
        try:
            uuid.UUID(flow_id)
        except ValueError:
            return [self._issue("subflow_not_selected", "pick a flow to run", "data.flow_id")]
        if ctx.contracts is None:
            return []
        contract = ctx.contracts.get(flow_id)
        if contract is None:
            return [
                self._issue(
                    "subflow_unavailable",
                    "the flow is missing, or has no published version",
                    "data.flow_id",
                )
            ]
        declared = {f.name for f in contract.inputs}
        issues = [
            self._issue(
                "unknown_subflow_input", f"the flow has no input '{name}'", f"data.inputs.{name}"
            )
            for name in self.data.inputs
            if name not in declared
        ]
        issues += [
            self._issue(
                "missing_subflow_input", f"input '{f.name}' needs a value", f"data.inputs.{f.name}"
            )
            for f in contract.inputs
            if f.required and f.default is None and not self.data.inputs.get(f.name, "").strip()
        ]
        return issues

    def output_names(self, ctx: NodeContext) -> set[str] | None:
        contract = (ctx.contracts or {}).get(self.data.flow_id)
        return None if contract is None else {o.name for o in contract.outputs}

    async def run(self, state: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        runtime = ctx.subflows
        if runtime is None:
            raise ValueError("subflows are not available here")
        limit = runtime.access.max_depth
        if limit and runtime.depth >= limit:
            raise ValueError(f"subflows are nested more than {limit} levels deep")
        scopes = {
            "input": state.get("input", {}),
            "vars": state.get("vars", {}),
            "nodes": state.get("nodes", {}),
        }
        payload: dict[str, Any] = {}
        for name, template in self.data.inputs.items():
            if not template.strip():
                continue
            try:
                payload[name] = render(template, scopes)
            except TemplateError as exc:
                raise ValueError(f"input '{name}': {exc}") from None
        graph = await runtime.access.load(self.data.flow_id)
        key = f"{runtime.scope}>{self.id}" if runtime.scope else self.id
        try:
            result = await runtime.execute(graph, payload, ctx, runtime, key)
        except InputValidationError as exc:
            raise ValueError(f"the flow rejected its input: {exc}") from None
        if result.status == "failed" or result.output is None:
            error = result.error
            where = f" at '{error.node_id}'" if error and error.node_id else ""
            raise ValueError(f"the flow failed{where}: {error.message if error else 'no output'}")
        return {"nodes": {self.id: {"output": result.output}}}
