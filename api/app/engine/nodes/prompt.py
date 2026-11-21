"""Asks a chat model one question and returns its text."""

import json
import uuid
from typing import Any, Literal

from pydantic import Field

from app.engine.base import StrictBaseModel
from app.engine.issues import Issue
from app.engine.llm import chat_completion, require_base_url
from app.engine.nodes.base import NodeContext, NodeModel
from app.engine.templates import TemplateError, render


class PromptData(StrictBaseModel):
    connection_id: str = ""
    # Empty: the connection's default model.
    model: str = ""
    system: str = ""
    prompt: str = ""
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1)
    timeout_seconds: int | None = Field(default=None, ge=1)


class PromptNode(NodeModel):
    type: Literal["prompt"]
    data: PromptData = Field(default_factory=PromptData)

    def templates(self) -> dict[str, str]:
        d = self.data
        return {"data.model": d.model, "data.system": d.system, "data.prompt": d.prompt}

    def connection_ids(self) -> set[str]:
        return {self.data.connection_id} if self.data.connection_id else set()

    def output_names(self, ctx: NodeContext) -> set[str] | None:
        return {"text", "model", "finish_reason", "usage"}

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
        model = render_text(d.model, scopes, "model").strip() or connection.values.get(
            "default_model", ""
        )
        if not model:
            raise ValueError("no model: set one in the node or a default model on the connection")
        messages = []
        if d.system.strip():
            messages.append({"role": "system", "content": render_text(d.system, scopes, "system")})
        messages.append({"role": "user", "content": render_text(d.prompt, scopes, "prompt")})
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
        )
        return {"nodes": {self.id: {"output": reply.model_dump()}}}


def render_text(template: str, scopes: dict[str, Any], field: str) -> str:
    try:
        value = render(template, scopes)
    except TemplateError as exc:
        raise ValueError(f"{field}: {exc}") from None
    return value if isinstance(value, str) else json.dumps(value)
