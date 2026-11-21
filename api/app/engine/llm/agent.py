"""A model that calls tools in a loop until it answers or a hard limit is reached."""

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from langchain_core.messages import BaseMessage, ToolMessage
from pydantic import Field

from app.engine.base import FrozenBaseModel
from app.engine.connections import ResolvedConnection
from app.engine.fields import FieldDef
from app.engine.llm.chat import OUT_OF_TOKENS, _reply, failure, open_chat
from app.security.ssrf import OutboundPolicy

logger = logging.getLogger(__name__)

TOOL_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAX_TOOLS = 64
FORMAT_REQUEST = "Now give your final answer again, in the required format."
Stop = Literal["answer", "max_iterations", "max_tokens", "timeout"]
ToolRunner = Callable[[str, dict[str, Any]], Awaitable[str]]


class ToolSpec(FrozenBaseModel):
    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})


class AgentLimits(FrozenBaseModel):
    max_iterations: int = Field(default=8, ge=1, le=50)
    max_total_tokens: int | None = Field(default=None, ge=1)
    max_seconds: float = Field(default=120, gt=0)
    max_tool_result_chars: int = Field(default=20_000, ge=1)


class ToolStep(FrozenBaseModel):
    name: str
    arguments: dict[str, Any]
    result: str
    is_error: bool = False


class AgentResult(FrozenBaseModel):
    """`text` is empty unless `stop` is "answer"; `steps` and `usage` cover work done so far."""

    text: str
    stop: Stop
    iterations: int
    steps: tuple[ToolStep, ...]
    model: str
    usage: dict[str, int]


def input_schema(inputs: list[FieldDef]) -> dict[str, Any]:
    """The JSON schema a model fills in to call a flow with these start inputs."""
    properties: dict[str, Any] = {}
    for field in inputs:
        schema: dict[str, Any] = {"type": "string" if field.type == "enum" else field.type}
        if field.type == "enum":
            schema["enum"] = field.values
        properties[field.name] = schema
    required = [f.name for f in inputs if f.required and f.default is None]
    return {"type": "object", "properties": properties, "required": required}


def _check_tools(tools: list[ToolSpec]) -> set[str]:
    if len(tools) > MAX_TOOLS:
        raise ValueError(f"an agent can have at most {MAX_TOOLS} tools")
    names = [t.name for t in tools]
    for name in names:
        if not TOOL_NAME.fullmatch(name):
            raise ValueError(f"tool name '{name}' must be 1-64 letters, digits, '_' or '-'")
    if len(set(names)) != len(names):
        raise ValueError("two tools have the same name")
    return set(names)


def _spec(tool: ToolSpec) -> dict[str, Any]:
    function = {"name": tool.name, "description": tool.description, "parameters": tool.parameters}
    return {"type": "function", "function": function}


async def _run_tool(
    run_tool: ToolRunner, names: set[str], name: str, arguments: dict[str, Any], limit: int
) -> ToolStep:
    if name not in names:
        result, is_error = f"error: no tool named '{name}'; use one of: {sorted(names)}", True
    else:
        try:
            result, is_error = await run_tool(name, arguments), False
        except ValueError as exc:
            result, is_error = f"error: {exc}", True
        except Exception:
            logger.exception("agent tool failed unexpectedly")
            result, is_error = "error: the tool failed unexpectedly", True
    if len(result) > limit:
        result = result[:limit] + "\n[result cut]"
    return ToolStep(name=name, arguments=arguments, result=result, is_error=is_error)


async def _ask(
    runnable: Any,
    thread: list[Any],
    policy: OutboundPolicy,
    connection: ResolvedConnection,
    response_format: dict[str, Any] | None = None,
) -> BaseMessage:
    extra = {"response_format": response_format} if response_format else {}
    try:
        async with asyncio.timeout(policy.timeout_seconds):
            return await runnable.ainvoke(thread, **extra)
    except Exception as exc:
        raise failure(exc, connection) from None


async def run_agent(
    policy: OutboundPolicy,
    connection: ResolvedConnection,
    *,
    model: str,
    instructions: str,
    messages: list[dict[str, str]],
    tools: list[ToolSpec],
    run_tool: ToolRunner,
    limits: AgentLimits | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    response_format: dict[str, Any] | None = None,
) -> AgentResult:
    """Raises ValueError with a message a flow author can act on. A tool's own failure is not
    raised: the model is told and can try something else. Hitting a limit is a `stop` value.

    `response_format` costs one extra call without tools after the answer: the SDK refuses a
    response format together with tools that are not strict."""
    limits = limits or AgentLimits()
    names = _check_tools(tools)
    chat, client = await open_chat(
        policy, connection, model=model, temperature=temperature, max_tokens=max_tokens
    )
    bound = chat.bind_tools([_spec(t) for t in tools]) if tools else chat
    thread: list[Any] = (
        [{"role": "system", "content": instructions}] if instructions.strip() else []
    )
    thread.extend(messages)
    steps: list[ToolStep] = []
    usage: dict[str, int] = {}
    served = model
    text, stop, iterations = "", "max_iterations", 0
    try:
        async with asyncio.timeout(limits.max_seconds) as deadline:
            for iterations in range(1, limits.max_iterations + 1):
                message = await _ask(bound, thread, policy, connection)
                reply = _reply(message, model)
                served = reply.model
                for key, value in reply.usage.items():
                    usage[key] = usage.get(key, 0) + value
                thread.append(message)
                calls = [
                    *((c["id"], c["name"], c["args"]) for c in message.tool_calls),
                    *(
                        (c.get("id") or "", c.get("name") or "", None)
                        for c in message.invalid_tool_calls
                    ),
                ]
                if not calls:
                    if not reply.text.strip() and reply.finish_reason == "length":
                        raise ValueError(OUT_OF_TOKENS)
                    text, stop = reply.text, "answer"
                    if response_format:
                        thread.append({"role": "user", "content": FORMAT_REQUEST})
                        final = await _ask(chat, thread, policy, connection, response_format)
                        shaped = _reply(final, model)
                        text = shaped.text
                        for key, value in shaped.usage.items():
                            usage[key] = usage.get(key, 0) + value
                    break
                if (
                    limits.max_total_tokens
                    and usage.get("total_tokens", 0) >= limits.max_total_tokens
                ):
                    stop = "max_tokens"
                    break
                if iterations == limits.max_iterations:
                    break
                for call_id, name, arguments in calls:
                    if arguments is None:
                        step = ToolStep(
                            name=name,
                            arguments={},
                            result="error: the arguments were not valid JSON",
                            is_error=True,
                        )
                    else:
                        step = await _run_tool(
                            run_tool, names, name, arguments, limits.max_tool_result_chars
                        )
                    steps.append(step)
                    thread.append(ToolMessage(content=step.result, tool_call_id=call_id))
    except TimeoutError:
        if not deadline.expired():
            raise
        stop = "timeout"
    finally:
        await client.aclose()
    return AgentResult(
        text=text,
        stop=stop,  # type: ignore[arg-type]
        iterations=iterations,
        steps=tuple(steps),
        model=served,
        usage=usage,
    )
