from typing import Any, ClassVar, Literal

from pydantic import Field

from app.engine import expressions
from app.engine.base import StrictBaseModel
from app.engine.issues import Issue
from app.engine.nodes.base import NodeContext, NodeModel


class ConditionData(StrictBaseModel):
    expression: str = ""  # CEL; must evaluate to a boolean


class ConditionNode(NodeModel):
    type: Literal["condition"]
    data: ConditionData = Field(default_factory=ConditionData)

    handles: ClassVar[tuple[str, ...]] = ("true", "false")

    def expressions(self) -> dict[str, str]:
        return {"data.expression": self.data.expression}

    def check(self, ctx: NodeContext) -> list[Issue]:
        try:
            compiled = expressions.compile(self.data.expression)
        except expressions.ExpressionError:
            return []  # the validator reports compile errors for every expression
        # a dynamic result (DYN) is checked when the node runs
        if compiled.return_type in ("BOOL", "DYN"):
            return []
        return [
            Issue(
                code="expression_not_boolean",
                message=f"expression must be true or false, not {compiled.return_type.lower()}",
                node_id=self.id,
                field="data.expression",
            )
        ]

    async def run(self, state: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        scope = {name: state.get(name, {}) for name in expressions.SCOPES}
        result = expressions.evaluate(expressions.compile(self.data.expression), scope)
        if not isinstance(result, bool):
            raise ValueError(f"expression must be true or false, got {result!r}")
        output = {"expression": self.data.expression, "result": result}
        return {"nodes": {self.id: {"output": output}}}

    def route(self, state: dict[str, Any]) -> str:
        return "true" if state["nodes"][self.id]["output"]["result"] else "false"
