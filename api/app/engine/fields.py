"""Typed field definitions shared by the graph, node settings and input validation."""

from typing import Any, Literal

from pydantic import model_validator

from app.engine.base import StrictBaseModel

FieldType = Literal["string", "number", "boolean", "object", "array", "enum"]


class TypedField(StrictBaseModel):
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


class Variable(StrictBaseModel):
    name: str
    type: FieldType
    initial: Any = None
