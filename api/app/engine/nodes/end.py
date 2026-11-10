from typing import Any, ClassVar, Literal

from pydantic import Field

from app.engine.base import StrictBaseModel
from app.engine.fields import TypedField
from app.engine.inputs import check_value
from app.engine.issues import Issue
from app.engine.nodes.base import NodeContext, NodeModel
from app.engine.templates import render


class OutputDef(TypedField):
    value: str  # template, e.g. "{{ input.amount }}"


class EndData(StrictBaseModel):
    outputs: list[OutputDef] = Field(default_factory=list)


class EndNode(NodeModel):
    type: Literal["end"]
    data: EndData = Field(default_factory=EndData)

    min_count: ClassVar[int] = 1
    accepts_outgoing: ClassVar[bool] = False

    def templates(self) -> dict[str, str]:
        return {f"data.outputs.{o.name}.value": o.value for o in self.data.outputs}

    @classmethod
    def check_group(cls, nodes: list["EndNode"]) -> list[Issue]:
        shapes = {tuple((o.name, o.type) for o in n.data.outputs) for n in nodes}
        if len(shapes) > 1:
            return [
                Issue(
                    code="end_outputs_differ", message="all end nodes must declare the same outputs"
                )
            ]
        return []

    async def run(self, state: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        scopes = {"input": state["input"], "vars": state.get("vars", {})}
        output: dict[str, Any] = {}
        for out in self.data.outputs:
            try:
                output[out.name] = check_value(out, render(out.value, scopes))
            except ValueError as exc:
                raise ValueError(f"output '{out.name}': {exc}") from exc
        # a thread keeps state between runs: clear input so an empty submit cannot reuse it
        return {"_output": output, "input": {}, "nodes": {self.id: {"output": output}}}
