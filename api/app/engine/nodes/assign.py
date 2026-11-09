from typing import Any, Literal

from pydantic import Field

from app.engine.base import StrictBaseModel
from app.engine.inputs import check_value
from app.engine.issues import Issue
from app.engine.nodes.base import NodeContext, NodeModel
from app.engine.templates import render


class Assignment(StrictBaseModel):
    variable: str
    value: str  # template, e.g. "{{ input.amount }}"; a lone reference keeps its type


class AssignData(StrictBaseModel):
    assignments: list[Assignment] = Field(default_factory=list)


class AssignNode(NodeModel):
    type: Literal["assign"]
    data: AssignData = Field(default_factory=AssignData)

    def templates(self) -> dict[str, str]:
        return {f"data.assignments.{i}.value": a.value for i, a in enumerate(self.data.assignments)}

    def check(self, ctx: NodeContext) -> list[Issue]:
        declared = {v.name for v in ctx.variables}
        return [
            Issue(
                code="unknown_variable",
                message=f"'{a.variable}' is not a declared variable",
                node_id=self.id,
                field=f"data.assignments.{i}.variable",
            )
            for i, a in enumerate(self.data.assignments)
            if a.variable not in declared
        ]

    async def run(self, state: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        declared = {v.name: v for v in ctx.variables}
        variables = dict(state.get("vars", {}))
        assigned: dict[str, Any] = {}
        for a in self.data.assignments:
            scopes = {"input": state.get("input", {}), "vars": variables}  # later ones see earlier
            try:
                value = check_value(declared[a.variable], render(a.value, scopes))
            except ValueError as exc:
                raise ValueError(f"assignment '{a.variable}': {exc}") from exc
            variables[a.variable] = assigned[a.variable] = value
        return {"vars": variables, "nodes": {self.id: {"output": assigned}}}
