"""Asks a chat model a question and returns its answer as typed fields."""

import json
import re
import uuid
from typing import Any, Literal

from pydantic import Field

from app.engine.base import StrictBaseModel
from app.engine.issues import Issue
from app.engine.llm import (
    SUPPORTED_TYPES,
    SchemaField,
    chat_completion,
    json_instruction,
    parse_answer,
    require_base_url,
    response_format,
)
from app.engine.nodes.base import NodeContext, NodeModel
from app.engine.templates import TemplateError, render

FIELD_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class StructuredOutputData(StrictBaseModel):
    connection_id: str = ""
    # Empty: the connection's default model.
    model: str = ""
    system: str = ""
    prompt: str = ""
    fields: list[SchemaField] = Field(default_factory=list)
    # "schema" asks the provider to enforce the structure; "json" only asks for a JSON object.
    mode: Literal["schema", "json"] = "schema"
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1)
    timeout_seconds: int | None = Field(default=None, ge=1)


class StructuredOutputNode(NodeModel):
    type: Literal["structured_output"]
    data: StructuredOutputData = Field(default_factory=StructuredOutputData)

    def templates(self) -> dict[str, str]:
        d = self.data
        return {"data.model": d.model, "data.system": d.system, "data.prompt": d.prompt}

    def connection_ids(self) -> set[str]:
        return {self.data.connection_id} if self.data.connection_id else set()

    def output_names(self, ctx: NodeContext) -> set[str] | None:
        return {f.name for f in self.data.fields}

    def check(self, ctx: NodeContext) -> list[Issue]:
        d = self.data
        found: list[tuple[str, str, str]] = []
        if not d.connection_id:
            found.append(("missing_connection", "pick a connection", "data.connection_id"))
        else:
            try:
                uuid.UUID(d.connection_id)
            except ValueError:
                found.append(
                    ("invalid_connection", "pick a connection again", "data.connection_id")
                )
        if not d.prompt.strip():
            found.append(("missing_prompt", "enter the prompt to send", "data.prompt"))
        if not d.fields:
            found.append(("missing_fields", "add at least one field to return", "data.fields"))
        seen: set[str] = set()
        for index, f in enumerate(d.fields):
            where = f"data.fields.{index}"
            if not FIELD_NAME.fullmatch(f.name):
                found.append(("invalid_field_name", f"'{f.name}' is not a valid name", where))
            elif f.name in seen:
                found.append(("duplicate_field", f"'{f.name}' is used twice", where))
            seen.add(f.name)
            if f.type not in SUPPORTED_TYPES:
                found.append(
                    ("unsupported_field_type", f"'{f.type}' fields are not supported", where)
                )
        return [Issue(code=c, message=m, node_id=self.id, field=f) for c, m, f in found]

    async def run(self, state: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        d = self.data
        if ctx.outbound is None:
            raise ValueError("outbound requests are not configured")
        connection = ctx.secrets.connections.get(d.connection_id)
        if connection is None:
            raise ValueError("the connection is not available; pick it again in the node")
        require_base_url(connection)
        scopes = {
            "input": state.get("input", {}),
            "vars": state.get("vars", {}),
            "nodes": state.get("nodes", {}),
            "connection": connection.values,
        }
        model = _text(d.model, scopes, "model").strip() or connection.values.get(
            "default_model", ""
        )
        if not model:
            raise ValueError("no model: set one in the node or a default model on the connection")
        system = _text(d.system, scopes, "system").strip() if d.system.strip() else ""
        if d.mode == "json":
            system = f"{system}\n\n{json_instruction(d.fields)}".strip()
        messages = [{"role": "system", "content": system}] if system else []
        messages.append({"role": "user", "content": _text(d.prompt, scopes, "prompt")})
        policy = ctx.outbound
        if d.timeout_seconds:
            policy = policy.model_copy(
                update={"timeout_seconds": min(d.timeout_seconds, policy.timeout_seconds)}
            )
        reply = await chat_completion(
            policy,
            connection,
            model=model,
            messages=messages,
            temperature=d.temperature,
            max_tokens=d.max_tokens,
            response_format=response_format(d.fields, d.mode),
        )
        return {"nodes": {self.id: {"output": parse_answer(reply.text, d.fields)}}}


def _text(template: str, scopes: dict[str, Any], field: str) -> str:
    try:
        value = render(template, scopes)
    except TemplateError as exc:
        raise ValueError(f"{field}: {exc}") from None
    return value if isinstance(value, str) else json.dumps(value)
