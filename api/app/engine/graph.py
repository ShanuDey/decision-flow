"""Flow graph JSON contract (graph-schema.md). Pure models: no DB, no web framework."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FieldType = Literal["string", "number", "boolean", "object", "array", "enum"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TypedField(_Strict):
    name: str
    type: FieldType
    values: list[str] | None = None

    @model_validator(mode="after")
    def _enum_needs_values(self) -> "TypedField":
        if self.type == "enum" and not self.values:
            raise ValueError("enum fields need a non-empty 'values' list")
        return self


class FieldDef(TypedField):
    required: bool = True
    default: Any = None


class Variable(_Strict):
    name: str
    type: FieldType
    initial: Any = None


class Position(_Strict):
    x: float = 0
    y: float = 0


class _NodeBase(_Strict):
    id: str
    name: str | None = None  # defaults to the type; unique per flow
    position: Position = Field(default_factory=Position)


class StartData(_Strict):
    inputs: list[FieldDef] = Field(default_factory=list)


class StartNode(_NodeBase):
    type: Literal["start"]
    data: StartData = Field(default_factory=StartData)


class OutputDef(TypedField):
    value: str  # template, e.g. "{{ input.amount }}"


class EndData(_Strict):
    outputs: list[OutputDef] = Field(default_factory=list)


class EndNode(_NodeBase):
    type: Literal["end"]
    data: EndData = Field(default_factory=EndData)


Node = Annotated[StartNode | EndNode, Field(discriminator="type")]


class Edge(_Strict):
    id: str
    source: str
    target: str
    sourceHandle: str | None = None


class Graph(_Strict):
    schema_version: Literal[1]
    variables: list[Variable] = Field(default_factory=list)
    nodes: list[Node]
    edges: list[Edge] = Field(default_factory=list)
