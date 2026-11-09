"""Validate a run's input payload against the Start node's declared fields (ADR 0014)."""

import math
from dataclasses import dataclass
from typing import Any

from app.engine.graph import FieldDef, TypedField


@dataclass(frozen=True)
class InputIssue:
    field: str
    message: str


class InputValidationError(Exception):
    def __init__(self, issues: list[InputIssue]) -> None:
        super().__init__("; ".join(f"{i.field}: {i.message}" for i in issues))
        self.issues = issues


def check_value(field: TypedField, value: Any) -> Any:
    """Return the value to use for `field`, or raise ValueError(message) if it is not acceptable.

    Strict: no coercion, so "5" is not a number. The flow is a typed function (ADR 0014).
    """
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
    """Validated input with defaults applied; raises InputValidationError naming each bad field."""
    issues: list[InputIssue] = []
    result: dict[str, Any] = {}
    declared = {f.name for f in fields}

    for name in payload:
        if name not in declared:
            issues.append(InputIssue(name, "unknown input field"))

    for field in fields:
        if field.name not in payload or payload[field.name] is None:
            if field.default is not None:
                result[field.name] = field.default
            elif field.required:
                issues.append(InputIssue(field.name, "required"))
            continue
        try:
            result[field.name] = check_value(field, payload[field.name])
        except ValueError as exc:
            issues.append(InputIssue(field.name, str(exc)))

    if issues:
        raise InputValidationError(issues)
    return result
