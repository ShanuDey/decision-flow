"""Turns declared fields into a JSON Schema for the model, and checks the model's answer."""

import json
import re
from typing import Any, Literal

from app.engine.fields import TypedField
from app.engine.inputs import check_value

# `object` is left out: a strict schema has to say what is inside it.
SUPPORTED_TYPES = ("string", "number", "boolean", "enum", "array")
FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)


class SchemaField(TypedField):
    description: str = ""


def json_schema(fields: list[SchemaField]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for f in fields:
        match f.type:
            case "enum":
                prop: dict[str, Any] = {"type": "string", "enum": list(f.values or [])}
            case "array":
                prop = {"type": "array", "items": {"type": "string"}}
            case _:
                prop = {"type": f.type}
        if f.description.strip():
            prop["description"] = f.description.strip()
        properties[f.name] = prop
    return {
        "type": "object",
        "properties": properties,
        "required": [f.name for f in fields],
        "additionalProperties": False,
    }


def response_format(fields: list[SchemaField], mode: Literal["schema", "json"]) -> dict[str, Any]:
    if mode == "json":
        return {"type": "json_object"}
    schema = json_schema(fields)
    return {
        "type": "json_schema",
        "json_schema": {"name": "result", "strict": True, "schema": schema},
    }


def json_instruction(fields: list[SchemaField]) -> str:
    schema = json.dumps(json_schema(fields), separators=(",", ":"))
    return (
        f"Reply with a single JSON object that matches this JSON Schema, and nothing else: {schema}"
    )


def parse_answer(text: str, fields: list[SchemaField]) -> dict[str, Any]:
    """Raises ValueError naming every field the answer gets wrong."""
    body = text.strip()
    if fenced := FENCE.match(body):
        body = fenced.group(1)
    try:
        data = json.loads(body)
    except ValueError:
        raise ValueError("the model did not answer with JSON") from None
    if not isinstance(data, dict):
        raise ValueError("the model did not answer with a JSON object")
    problems: list[str] = []
    result: dict[str, Any] = {}
    for f in fields:
        if f.name not in data:
            problems.append(f"{f.name}: missing")
            continue
        try:
            value = check_value(f, data[f.name])
            if f.type == "array" and not all(isinstance(item, str) for item in value):
                raise ValueError("expected a list of text")
            result[f.name] = value
        except ValueError as exc:
            problems.append(f"{f.name}: {exc}")
    if problems:
        raise ValueError("the answer does not match the structure: " + "; ".join(problems))
    return result
