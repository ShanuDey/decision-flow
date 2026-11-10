import math
from typing import Any

from app.engine.base import FrozenBaseModel
from app.engine.fields import FieldDef, TypedField


class InputIssue(FrozenBaseModel):
    field: str
    message: str


class InputValidationError(Exception):
    def __init__(self, issues: list[InputIssue]) -> None:
        super().__init__("; ".join(f"{i.field}: {i.message}" for i in issues))
        self.issues = issues


def check_value(field: TypedField, value: Any) -> Any:
    """Strict: no coercion ("5" is not a number); raises ValueError(message) if unacceptable."""
    match field.type:
        case "string":
            ok = isinstance(value, str)
        case "number":
            # bool is an int subclass; NaN/inf are not valid JSON numbers
            ok = (
                isinstance(value, int | float)
                and not isinstance(value, bool)
                and math.isfinite(value)
            )
        case "boolean":
            ok = isinstance(value, bool)
        case "object":
            ok = isinstance(value, dict)
        case "array":
            ok = isinstance(value, list)
        case "enum":
            if value not in (field.values or []):
                raise ValueError(f"must be one of {field.values}")
            return value
    if not ok:
        raise ValueError(f"expected {field.type}")
    return value


def validate_input(fields: list[FieldDef], payload: dict[str, Any]) -> dict[str, Any]:
    issues: list[InputIssue] = []
    result: dict[str, Any] = {}
    declared = {f.name for f in fields}

    for name in payload:
        if name not in declared:
            issues.append(InputIssue(field=name, message="unknown input field"))

    for field in fields:
        if field.name not in payload or payload[field.name] is None:
            if field.default is not None:
                result[field.name] = field.default
            elif field.required:
                issues.append(InputIssue(field=field.name, message="required"))
            continue
        try:
            result[field.name] = check_value(field, payload[field.name])
        except ValueError as exc:
            issues.append(InputIssue(field=field.name, message=str(exc)))

    if issues:
        raise InputValidationError(issues)
    return result
