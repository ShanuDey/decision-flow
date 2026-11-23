"""One agent turn as AG-UI events, reusing our turn code so limits and tracing match."""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from ag_ui.core import (
    BaseEvent,
    CustomEvent,
    RunAgentInput,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)

from app.agents import service
from app.agents.models import Agent, AgentThread
from app.engine.llm import ToolStep
from app.errors import ApiError
from app.runs.slots import RunSlots

logger = logging.getLogger(__name__)


def new_user_text(run: RunAgentInput) -> str | None:
    """The text of the last user message. Earlier ones are ignored: the server owns the history."""
    for message in reversed(run.messages):
        if message.role != "user":
            continue
        content = message.content
        if isinstance(content, str):
            return content or None
        text = "".join(getattr(part, "text", "") for part in content or [])
        return text or None
    return None


class _Answer:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.open: int | None = None

    def _id(self, index: int) -> str:
        return f"{self.run_id}:m{index}"

    def token(self, index: int, text: str) -> list[BaseEvent]:
        events = [] if self.open == index else [*self.close(), self._start(index)]
        self.open = index
        return [*events, TextMessageContentEvent(message_id=self._id(index), delta=text)]

    def _start(self, index: int) -> BaseEvent:
        return TextMessageStartEvent(message_id=self._id(index), role="assistant")

    def close(self) -> list[BaseEvent]:
        if self.open is None:
            return []
        end = TextMessageEndEvent(message_id=self._id(self.open))
        self.open = None
        return [end]


def tool_events(run_id: str, number: int, step: ToolStep) -> list[BaseEvent]:
    call = f"{run_id}:t{number}"
    return [
        ToolCallStartEvent(tool_call_id=call, tool_call_name=step.name),
        ToolCallArgsEvent(tool_call_id=call, delta=json.dumps(step.arguments)),
        ToolCallEndEvent(tool_call_id=call),
        ToolCallResultEvent(
            message_id=f"{call}:result", tool_call_id=call, content=step.result, role="tool"
        ),
    ]


KEEP_ALIVE = ": keep-alive\n\n"
# A quiet answer stream sends a comment line this often so a proxy does not close it.
KEEP_ALIVE_SECONDS = 15


async def with_keep_alive(chunks: AsyncIterator[str], every: float) -> AsyncIterator[str]:
    """The chunks, with a comment line whenever none arrives for `every` seconds."""
    chunk_iter = chunks.__aiter__()
    pending = asyncio.ensure_future(chunk_iter.__anext__())
    try:
        while True:
            done, _ = await asyncio.wait({pending}, timeout=every)
            if not done:
                yield KEEP_ALIVE
                continue
            try:
                chunk = pending.result()
            except StopAsyncIteration:
                return
            yield chunk
            pending = asyncio.ensure_future(chunk_iter.__anext__())
    finally:
        pending.cancel()


async def run_events(
    ctx: service.TurnContext,
    agent: Agent,
    thread: AgentThread,
    content: str,
    slots: RunSlots,
) -> AsyncIterator[BaseEvent]:
    run_id = str(uuid.uuid4())
    queue: asyncio.Queue[BaseEvent | None] = asyncio.Queue()
    answer = _Answer(run_id)
    tools = 0

    async def put(*events: BaseEvent) -> None:
        for event in events:
            await queue.put(event)

    async def on_token(index: int, text: str) -> None:
        await put(*answer.token(index, text))

    async def on_step(step: ToolStep) -> None:
        nonlocal tools
        tools += 1
        await put(*answer.close(), *tool_events(run_id, tools, step))

    async def work() -> None:
        try:
            async with slots.hold(ctx.member.workspace_id):
                user, reply = await service.run_turn(ctx, agent, thread, content, on_step, on_token)
            stored: dict[str, Any] = {
                "user_message": service.info(user).model_dump(mode="json"),
                "reply": service.info(reply).model_dump(mode="json"),
            }
            await put(
                *answer.close(),
                CustomEvent(name="message.stored", value=stored),
                RunFinishedEvent(
                    thread_id=str(thread.id), run_id=run_id, result={"messageId": str(reply.id)}
                ),
            )
        except ApiError as exc:
            await put(*answer.close(), RunErrorEvent(message=exc.body.message, code=exc.body.code))
        except Exception:
            logger.exception("agent turn failed unexpectedly")
            failed = RunErrorEvent(message="The agent failed unexpectedly", code="internal_error")
            await put(*answer.close(), failed)
        finally:
            await queue.put(None)

    yield RunStartedEvent(thread_id=str(thread.id), run_id=run_id)
    task = asyncio.create_task(work())
    try:
        while (event := await queue.get()) is not None:
            yield event
    finally:
        task.cancel()
