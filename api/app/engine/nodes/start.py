"""Start: declares the flow's typed input and seeds the run's variables."""

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, StrictBool, StrictFloat, StrictInt, StrictStr, create_model

from app.engine.base import StrictBaseModel
from app.engine.fields import FieldDef
from app.engine.inputs import InputValidationError, validate_input
from app.engine.nodes.base import NodeContext, NodeModel


class StartData(StrictBaseModel):
    inputs: list[FieldDef] = Field(default_factory=list)


def _annotation(field: FieldDef) -> Any:
    # strict, like check_value: "5" is not a number
    match field.type:
        case "string":
            return StrictStr
        case "number":
            return StrictInt | StrictFloat
        case "boolean":
            return StrictBool
        case "object":
            return dict[str, Any]
        case "array":
            return list[Any]
        case "enum":
            return Literal[tuple(field.values or [])]


class StartNode(NodeModel):
    type: Literal["start"]
    data: StartData = Field(default_factory=StartData)

    min_count: ClassVar[int] = 1
    max_count: ClassVar[int | None] = 1
    accepts_incoming: ClassVar[bool] = False

    def input_model(self) -> type[BaseModel]:
        """Typed form of the input, so tools like Studio can show the fields.

        Documentation only: LangGraph does not validate against it; `run` does.
        """
        fields: dict[str, Any] = {}
        for i, f in enumerate(self.data.inputs):
            kind = _annotation(f)
            if f.default is not None:
                annotation, default = kind, f.default
            elif f.required:
                annotation, default = kind, ...
            else:
                annotation, default = kind | None, None
            # aliases keep any input name valid, even ones that are not Python identifiers
            fields[f"f{i}"] = (annotation, Field(default, alias=f.name))
        return create_model("Input", **fields)

    async def run(self, state: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        # run_flow already validated; repeating gives direct graph callers (Studio) the defaults
        try:
            inputs = validate_input(self.data.inputs, state.get("input") or {})
        except InputValidationError as exc:
            raise ValueError(str(exc)) from exc
        return {
            "input": inputs,
            "vars": {v.name: v.initial for v in ctx.variables},
            "nodes": {self.id: {"output": inputs}},
        }
