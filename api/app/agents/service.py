"""Agent resources and their conversations. Logic lives here; router.py only does HTTP."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from app.agents.caller import ANON_PREFIX, Caller
from app.agents.models import Agent, AgentMessage, AgentThread
from app.agents.schemas import (
    AgentCreate,
    AgentSettings,
    AgentSummary,
    AgentUpdate,
    MessageInfo,
    ThreadSummary,
    ToolCallInfo,
)
from app.agents.store import AgentStore, NameTaken, NewMessage, ThreadBusy
from app.connections.store import ConnectionStore
from app.engine.agent_tools import AgentTool, FlowTools, check_tools
from app.engine.compiler import compile_graph
from app.engine.llm import AgentLimits, ChatReply, ToolStep, require_base_url, run_agent
from app.engine.llm.agent import TokenListener
from app.engine.nodes.agent import STOPPED
from app.engine.observer import Observer, ScopedObserver
from app.engine.redact import Redactor
from app.engine.run_secrets import RunSecrets
from app.engine.runtime import run_flow
from app.errors import ApiError
from app.flows.store import FlowStore
from app.flows.subflows import SubflowSource
from app.limits import Limits
from app.runs.schemas import RunSteps
from app.runs.service import SecretLoader, TraceReader, trace_steps
from app.security.ssrf import OutboundPolicy
from app.workspaces.schemas import Member

SETTING_KEYS = (
    "max_iterations",
    "max_total_tokens",
    "max_seconds",
    "temperature",
    "max_tokens",
    "timeout_seconds",
)
# Only the latest turns are sent back to the model, so a long thread stays affordable.
HISTORY_MESSAGES = 40
HISTORY_CHARS = 60_000
TITLE_CHARS = 60

StepListener = Callable[[ToolStep], Awaitable[None]]


def not_found(what: str = "Agent") -> ApiError:
    return ApiError(404, "not_found", f"{what} not found")


def summarize(agent: Agent) -> AgentSummary:
    return AgentSummary(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        connection_id=agent.connection_id,
        model=agent.model,
        instructions=agent.instructions,
        tools=[AgentTool.model_validate(t) for t in agent.tools],
        created_at=agent.created_at,
        updated_at=agent.updated_at,
        **{k: v for k, v in agent.settings.items() if k in SETTING_KEYS},
    )


def _fields(body: AgentSettings) -> dict[str, Any]:
    return {
        "description": body.description,
        "connection_id": body.connection_id,
        "model": body.model,
        "instructions": body.instructions,
        "tools": [t.model_dump() for t in body.tools],
        "settings": {k: getattr(body, k) for k in SETTING_KEYS},
    }


async def _check(
    body: AgentSettings, connections: ConnectionStore, flows: FlowStore, member: Member
) -> None:
    if body.connection_id and await connections.get(member, body.connection_id) is None:
        raise ApiError(
            422,
            "connection_not_found",
            "That connection does not exist",
            {"field": "connection_id"},
        )
    if problem := check_tools(body.tools):
        raise ApiError(422, "invalid_tools", problem, {"field": "tools"})
    for tool in body.tools:
        if await flows.get_flow(member, uuid.UUID(tool.flow_id)) is None:
            raise ApiError(
                422,
                "tool_flow_not_found",
                f"The flow for tool {tool.name} does not exist",
                {"field": "tools"},
            )


def name_taken() -> ApiError:
    return ApiError(409, "agent_name_taken", "You already have an agent with that name.")


async def create_agent(
    store: AgentStore,
    connections: ConnectionStore,
    flows: FlowStore,
    member: Member,
    body: AgentCreate,
) -> Agent:
    await _check(body, connections, flows, member)
    try:
        return await store.add(member, body.name, _fields(body))
    except NameTaken:
        raise name_taken() from None


async def require_agent(store: AgentStore, member: Member, agent_id: uuid.UUID) -> Agent:
    agent = await store.get(member, agent_id)
    if agent is None:
        raise not_found()
    return agent


async def update_agent(
    store: AgentStore,
    connections: ConnectionStore,
    flows: FlowStore,
    member: Member,
    agent_id: uuid.UUID,
    body: AgentUpdate,
) -> Agent:
    agent = await require_agent(store, member, agent_id)
    current = summarize(agent).model_dump(exclude={"id", "name", "created_at", "updated_at"})
    current["tools"] = [t.model_dump() for t in summarize(agent).tools]
    sent = {k: getattr(body, k) for k in body.model_fields_set if k != "name"}
    # Null clears only what can be empty; for the rest it means "leave as it is".
    clearable = {"connection_id", *SETTING_KEYS} - {"max_iterations"}
    merged = current | {k: v for k, v in sent.items() if v is not None or k in clearable}
    settings = AgentSettings.model_validate(merged)
    await _check(settings, connections, flows, member)
    try:
        updated = await store.replace(member, agent_id, body.name or agent.name, _fields(settings))
    except NameTaken:
        raise name_taken() from None
    if updated is None:
        raise not_found()
    return updated


async def delete_agent(store: AgentStore, member: Member, agent_id: uuid.UUID) -> None:
    if not await store.delete(member, agent_id):
        raise not_found()


def summarize_thread(thread: AgentThread) -> ThreadSummary:
    return ThreadSummary.model_validate(thread, from_attributes=True)


def info(message: AgentMessage) -> MessageInfo:
    steps = None if message.steps is None else [ToolCallInfo(**s) for s in message.steps]
    return MessageInfo(
        id=message.id,
        seq=message.seq,
        role=message.role,  # type: ignore[arg-type]
        content=message.content,
        steps=steps,
        usage=message.usage,
        model=message.model,
        traced=message.trace_id is not None,
        created_at=message.created_at,
    )


async def require_thread(
    store: AgentStore,
    member: Member,
    caller: Caller,
    agent_id: uuid.UUID,
    thread_id: uuid.UUID,
) -> AgentThread:
    thread = await store.get_thread(member, agent_id, thread_id)
    if thread is None:
        raise not_found("Thread")
    if caller.external_user_id is not None and thread.external_user_id != caller.external_user_id:
        raise not_found("Thread")
    return thread


def turn_limits(settings: dict[str, Any], cap_seconds: int) -> AgentLimits:
    """The agent's own limits, with the time one answer may take held under the run timeout."""
    chosen = {
        k: settings[k]
        for k in ("max_iterations", "max_total_tokens", "max_seconds")
        if settings.get(k)
    }
    if cap_seconds:
        chosen["max_seconds"] = min(
            chosen.get("max_seconds", AgentLimits().max_seconds), cap_seconds
        )
    return AgentLimits(**chosen)


def new_thread_owner(caller: Caller) -> str | None:
    """The external user id a new conversation gets: none for a team member."""
    if caller.source == "web":
        return None
    return caller.external_user_id or f"{ANON_PREFIX}{uuid.uuid4().hex}"


def listing_filter(caller: Caller) -> str | None:
    """The person a listing is narrowed to. An API key must always name one."""
    if caller.source == "api" and caller.external_user_id is None:
        raise ApiError(
            422,
            "external_user_id_required",
            "Name the person whose conversations to list with X-External-User-Id",
        )
    return caller.external_user_id


def _history(messages: list[AgentMessage]) -> list[dict[str, str]]:
    kept: list[dict[str, str]] = []
    size = 0
    for message in reversed(messages[-HISTORY_MESSAGES:]):
        size += len(message.content)
        if kept and size > HISTORY_CHARS:
            break
        kept.append({"role": message.role, "content": message.content})
    return kept[::-1]


class AgentTracer(Observer, Protocol):
    """Records one trace per turn: the engine's observer, plus a span for each model call."""

    trace_id: str | None

    async def span_started(self, key: str, name: str, kind: str, inputs: Any) -> None: ...

    async def span_finished(self, key: str, ok: bool, error: str | None, outputs: Any) -> None: ...


TracerFactory = Callable[[str], AgentTracer]


class TurnContext:
    """What one turn needs from the request: who is asking and how to reach the outside."""

    def __init__(
        self,
        store: AgentStore,
        flows: FlowStore,
        member: Member,
        limits: Limits,
        outbound: OutboundPolicy,
        load_secrets: SecretLoader,
        new_tracer: TracerFactory,
    ) -> None:
        self.store, self.member, self.limits = store, member, limits
        self.outbound, self.load_secrets, self.new_tracer = outbound, load_secrets, new_tracer
        self.subflows = SubflowSource(flows, member, limits, outbound)


def _redact(message: str, secrets: RunSecrets) -> str:
    return Redactor(secrets).text(message)


class _ModelSpans:
    """Turns the engine's model-call hooks into trace spans, with secrets masked."""

    def __init__(self, tracer: AgentTracer, redactor: Redactor) -> None:
        self._tracer, self._redactor = tracer, redactor

    async def started(self, index: int, messages: list[dict[str, Any]]) -> None:
        inputs = self._redactor.apply({"messages": messages})
        await self._tracer.span_started(f"model-{index}", f"Model call {index}", "llm", inputs)

    async def finished(self, index: int, reply: ChatReply | None, error: str | None) -> None:
        outputs = None
        if reply is not None:
            outputs = {
                "text": reply.text,
                "model": reply.model,
                "finish_reason": reply.finish_reason,
                "usage": reply.usage,
            }
        await self._tracer.span_finished(
            f"model-{index}",
            error is None,
            self._redactor.text(error) if error else None,
            self._redactor.apply(outputs),
        )


async def run_turn(
    ctx: TurnContext,
    agent: Agent,
    thread: AgentThread,
    content: str,
    on_step: StepListener | None = None,
    on_token: TokenListener | None = None,
) -> tuple[AgentMessage, AgentMessage]:
    """Answers one user message and stores both messages; nothing is stored if it fails."""
    if agent.connection_id is None:
        raise ApiError(422, "agent_not_ready", "Pick a connection for this agent first")
    tools = [AgentTool.model_validate(t) for t in agent.tools]
    names, connection_ids = await ctx.subflows.needs([t.flow_id for t in tools])
    connection_ids.add(str(agent.connection_id))
    secrets = await ctx.load_secrets(names, connection_ids)
    connection = secrets.connections.get(str(agent.connection_id))
    if connection is None:
        raise ApiError(422, "agent_not_ready", "The connection of this agent no longer exists")
    try:
        require_base_url(connection)
        model = agent.model.strip() or connection.values.get("default_model", "")
        if not model:
            raise ValueError("no model: set one on the agent or a default model on the connection")
        flow_tools = await FlowTools.load(tools, ctx.subflows.load)
    except ValueError as exc:
        raise ApiError(422, "agent_not_ready", str(exc)) from None

    redactor = Redactor(secrets)
    tracer = ctx.new_tracer(agent.name)
    started = {"message": content, "agent": agent.name, "thread": str(thread.id)}
    await tracer.run_started(redactor.apply(started))
    calls = 0

    async def run_tool(name: str, arguments: dict[str, Any]) -> str:
        nonlocal calls
        calls += 1
        key = f"tool-{calls}"
        await tracer.span_started(key, name, "tool", redactor.apply(arguments))

        async def execute(graph: Any, payload: dict[str, Any]) -> Any:
            return await run_flow(
                compile_graph(graph),
                payload,
                ScopedObserver(tracer, key),
                ctx.limits.run_timeout_seconds,
                secrets,
                ctx.outbound,
                ctx.subflows.access,
            )

        try:
            result = await flow_tools.run(name, arguments, execute)
        except ValueError as exc:
            await tracer.span_finished(key, False, redactor.text(str(exc)), None)
            raise
        await tracer.span_finished(key, True, None, redactor.text(result))
        return result

    async def fail(error: ApiError) -> ApiError:
        await tracer.run_finished("failed", error.body.message)
        return error

    history = _history(await ctx.store.list_messages(thread.id))
    settings = agent.settings
    policy = ctx.outbound
    if settings.get("timeout_seconds"):
        policy = policy.model_copy(
            update={"timeout_seconds": min(settings["timeout_seconds"], policy.timeout_seconds)}
        )
    try:
        result = await run_agent(
            policy,
            connection,
            model=model,
            instructions=agent.instructions,
            messages=[*history, {"role": "user", "content": content}],
            tools=flow_tools.specs,
            run_tool=run_tool,
            limits=turn_limits(settings, ctx.limits.run_timeout_seconds),
            temperature=settings.get("temperature"),
            max_tokens=settings.get("max_tokens"),
            on_step=on_step,
            on_model=_ModelSpans(tracer, redactor),
            on_token=on_token,
        )
    except ValueError as exc:
        raise await fail(ApiError(502, "model_failed", _redact(str(exc), secrets))) from None
    if result.stop != "answer":
        raise await fail(ApiError(422, "agent_stopped", STOPPED[result.stop]))
    asked = NewMessage("user", content)
    answered = NewMessage(
        "assistant",
        result.text,
        steps=[s.model_dump() for s in result.steps],
        usage=result.usage,
        model=result.model,
        trace_id=tracer.trace_id,
    )
    try:
        stored = await ctx.store.add_messages(
            thread, [asked, answered], content.strip()[:TITLE_CHARS]
        )
    except ThreadBusy:
        raise await fail(
            ApiError(
                409, "thread_busy", "Another message in this thread was answered at the same time"
            )
        ) from None
    await tracer.run_finished("succeeded", None, {"answer": redactor.text(result.text)})
    return stored[0], stored[1]


async def message_steps(
    store: AgentStore,
    member: Member,
    caller: Caller,
    agent_id: uuid.UUID,
    thread_id: uuid.UUID,
    message_id: uuid.UUID,
    read: TraceReader,
) -> RunSteps:
    thread = await require_thread(store, member, caller, agent_id, thread_id)
    message = await store.get_message(thread.id, message_id)
    if message is None:
        raise not_found("Message")
    return await trace_steps(message.trace_id, message.created_at, read)
