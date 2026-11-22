"""A model that calls tools in a loop until it answers or a hard limit is reached."""

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any, Literal, Protocol

from langchain.agents import create_agent
from langchain.agents.middleware import after_model
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import BaseMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import Field

from app.engine.base import FrozenBaseModel
from app.engine.connections import ResolvedConnection
from app.engine.fields import FieldDef
from app.engine.llm.chat import OUT_OF_TOKENS, ChatReply, _reply, _text, failure, open_chat
from app.security.ssrf import OutboundPolicy

logger = logging.getLogger(__name__)

TOOL_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAX_TOOLS = 64
FORMAT_REQUEST = "Now give your final answer again, in the required format."
BAD_ARGUMENTS = "error: the arguments were not valid JSON"
Stop = Literal["answer", "max_iterations", "max_tokens", "timeout"]
ToolRunner = Callable[[str, dict[str, Any]], Awaitable[str]]
StepListener = Callable[["ToolStep"], Awaitable[None]]


class ModelListener(Protocol):
    """Told about each model call, so a trace can show them. Must not raise."""

    async def started(self, index: int, messages: list[dict[str, Any]]) -> None: ...

    async def finished(self, index: int, reply: ChatReply | None, error: str | None) -> None: ...


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
    config: dict[str, Any] | None = None,
) -> BaseMessage:
    extra = {"response_format": response_format} if response_format else {}
    try:
        async with asyncio.timeout(policy.timeout_seconds):
            return await runnable.ainvoke(thread, config=config, **extra)
    except Exception as exc:
        raise failure(exc, connection) from None


ROLES = {"human": "user", "ai": "assistant"}


def _brief(thread: list[Any]) -> list[dict[str, Any]]:
    """The conversation as plain role and content, tool calls by name."""
    brief: list[dict[str, Any]] = []
    for item in thread:
        if isinstance(item, dict):
            brief.append({"role": item.get("role"), "content": item.get("content")})
            continue
        entry: dict[str, Any] = {"role": ROLES.get(item.type, item.type), "content": _text(item)}
        if getattr(item, "tool_calls", None):
            entry["tool_calls"] = [c["name"] for c in item.tool_calls]
        brief.append(entry)
    return brief


class _ModelHooks(AsyncCallbackHandler):
    """Passes LangChain's model callbacks on to a ModelListener, errors in our own wording."""

    def __init__(self, listener: ModelListener, model: str, connection: ResolvedConnection) -> None:
        self.listener, self.model, self.connection, self.count = listener, model, connection, 0

    async def on_chat_model_start(self, serialized: Any, messages: Any, **kwargs: Any) -> None:
        self.count += 1
        await self.listener.started(self.count, _brief(list(messages[0])))

    async def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        reply = _reply(response.generations[0][0].message, self.model)
        await self.listener.finished(self.count, reply, None)

    async def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        mapped = failure(error, self.connection) if isinstance(error, Exception) else None
        await self.listener.finished(self.count, None, str(mapped or error))


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
    on_step: StepListener | None = None,
    on_model: ModelListener | None = None,
) -> AgentResult:
    """Raises ValueError with a message a flow author can act on. A tool's own failure is not
    raised: the model is told and can try something else. Hitting a limit is a `stop` value.

    The loop is LangChain's `create_agent`; what is ours is the guarded client, the limits, the
    error wording, and answering tool calls the library would drop. Tools run one at a time, in
    the order the model asked for them, because a flow may change something.

    `response_format` costs one extra call without tools after the answer: the SDK refuses a
    response format together with tools that are not strict."""
    limits = limits or AgentLimits()
    names = _check_tools(tools)
    chat, client = await open_chat(
        policy, connection, model=model, temperature=temperature, max_tokens=max_tokens
    )
    steps: list[ToolStep] = []
    stop = {"reason": "answer"}
    one_at_a_time = asyncio.Lock()

    async def record(step: ToolStep) -> None:
        steps.append(step)
        if on_step:
            await on_step(step)

    def make_tool(spec: ToolSpec) -> StructuredTool:
        async def call(**arguments: Any) -> str:
            async with one_at_a_time:
                step = await _run_tool(
                    run_tool, names, spec.name, arguments, limits.max_tool_result_chars
                )
                await record(step)
            return step.result

        return StructuredTool(
            name=spec.name,
            description=spec.description or spec.name,
            args_schema=spec.parameters,
            coroutine=call,
        )

    earlier = sum(1 for m in messages if m.get("role") == "assistant")

    @after_model(can_jump_to=["end", "model"])
    async def guard(state: Any, runtime: Any) -> dict[str, Any] | None:
        # Earlier assistant messages of the conversation are input, not work done in this run.
        ai = [m for m in state["messages"] if m.type == "ai"][earlier:]
        last = ai[-1]
        update: dict[str, Any] = {}
        invalid = list(last.invalid_tool_calls)
        if invalid:
            # The library would end the run on these with an empty answer; tell the model instead.
            replies = []
            for call in invalid:
                name = call.get("name") or ""
                await record(ToolStep(name=name, arguments={}, result=BAD_ARGUMENTS, is_error=True))
                replies.append(
                    ToolMessage(
                        content=BAD_ARGUMENTS, tool_call_id=call.get("id") or "", status="error"
                    )
                )
            update["messages"] = replies
        if not (last.tool_calls or invalid):
            return None
        total = sum((m.usage_metadata or {}).get("total_tokens", 0) for m in ai)
        if limits.max_total_tokens and total >= limits.max_total_tokens:
            stop["reason"] = "max_tokens"
            update["jump_to"] = "end"
        elif len(ai) >= limits.max_iterations:
            stop["reason"] = "max_iterations"
            update["jump_to"] = "end"
        elif invalid and not last.tool_calls:
            update["jump_to"] = "model"
        return update

    agent = create_agent(
        model=chat,
        tools=[make_tool(t) for t in tools],
        system_prompt=instructions if instructions.strip() else None,
        middleware=[guard],
    )
    config: dict[str, Any] = {"recursion_limit": limits.max_iterations * 6 + 20}
    hooks = _ModelHooks(on_model, model, connection) if on_model is not None else None
    if hooks:
        config["callbacks"] = [hooks]
    usage: dict[str, int] = {}
    served = model
    iterations = 0
    last_reply: ChatReply | None = None
    produced: list[Any] = []
    text = ""
    try:
        try:
            async with asyncio.timeout(limits.max_seconds) as deadline:
                async for update in agent.astream(
                    {"messages": messages}, config=config, stream_mode="updates"
                ):
                    for node, data in update.items():
                        for message in (data or {}).get("messages") or []:
                            produced.append(message)
                            if node == "tools" and getattr(message, "status", "") == "error":
                                # The library answered a call it could not run (an unknown tool).
                                await record(
                                    ToolStep(
                                        name=message.name or "",
                                        arguments={},
                                        result=str(message.content),
                                        is_error=True,
                                    )
                                )
                            if node == "model":
                                iterations += 1
                                last_reply = _reply(message, model)
                                served = last_reply.model
                                for key, value in last_reply.usage.items():
                                    usage[key] = usage.get(key, 0) + value
        except TimeoutError:
            if not deadline.expired():
                raise
            stop["reason"] = "timeout"
        except Exception as exc:
            raise failure(exc, connection) from None
        if stop["reason"] == "answer" and last_reply is not None:
            if not last_reply.text.strip() and last_reply.finish_reason == "length":
                raise ValueError(OUT_OF_TOKENS)
            text = last_reply.text
            if response_format:
                thread: list[Any] = (
                    [{"role": "system", "content": instructions}] if instructions.strip() else []
                )
                thread.extend(messages)
                thread.extend(produced)
                thread.append({"role": "user", "content": FORMAT_REQUEST})
                config_final = {"callbacks": [hooks]} if hooks else None
                final = await _ask(chat, thread, policy, connection, response_format, config_final)
                shaped = _reply(final, model)
                text = shaped.text
                for key, value in shaped.usage.items():
                    usage[key] = usage.get(key, 0) + value
    finally:
        await client.aclose()
    return AgentResult(
        text=text if stop["reason"] == "answer" else "",
        stop=stop["reason"],  # type: ignore[arg-type]
        iterations=iterations,
        steps=tuple(steps),
        model=served,
        usage=usage,
    )
