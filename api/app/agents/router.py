"""HTTP only: parsing, status codes, response shapes. Logic lives in service.py."""

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Any

from ag_ui.core import RunAgentInput
from ag_ui.encoder import EventEncoder
from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from app.agents import ag_ui, service
from app.agents.schemas import (
    AgentCreate,
    AgentList,
    AgentSummary,
    AgentUpdate,
    MessageRequest,
    ThreadDetail,
    ThreadList,
    ThreadSummary,
    TurnResponse,
)
from app.agents.store import AgentStore, get_agent_store
from app.connections.store import ConnectionStore, get_connection_store
from app.errors import ApiError, ErrorResponse
from app.flows.store import FlowStore, get_store
from app.limits import Limits, get_limits
from app.ratelimit import limit_runs
from app.runs.router import get_secret_loader, get_trace_reader
from app.runs.schemas import RunSteps
from app.runs.service import SecretLoader, TraceReader
from app.runs.slots import RunSlots, get_run_slots
from app.security.policy import outbound_policy
from app.settings import get_settings
from app.tracing import MlflowAgentObserver
from app.workspaces.deps import CurrentMember

router = APIRouter(tags=["agents"])
logger = logging.getLogger(__name__)
Store = Annotated[AgentStore, Depends(get_agent_store)]
Connections = Annotated[ConnectionStore, Depends(get_connection_store)]
Flows = Annotated[FlowStore, Depends(get_store)]

NOT_FOUND = {404: {"model": ErrorResponse}}
CONFLICT = {409: {"model": ErrorResponse}}
INVALID = {422: {"model": ErrorResponse}}
TOO_MANY = {429: {"model": ErrorResponse}}
MODEL_FAILED = {502: {"model": ErrorResponse}}
EVENT_STREAM = {200: {"content": {"text/event-stream": {}}, "description": "Server-sent events"}}


@router.get("/agents")
async def list_agents(store: Store, member: CurrentMember) -> AgentList:
    """Lists the workspace's agents by name."""
    return AgentList(items=[service.summarize(a) for a in await store.list_agents(member)])


@router.post("/agents", status_code=status.HTTP_201_CREATED, responses={**CONFLICT, **INVALID})
async def create_agent(
    body: AgentCreate, store: Store, connections: Connections, flows: Flows, member: CurrentMember
) -> AgentSummary:
    """Creates an agent: a model, instructions and published flows it may run as tools."""
    created = await service.create_agent(store, connections, flows, member, body)
    return service.summarize(created)


@router.get("/agents/{agent_id}", responses=NOT_FOUND)
async def get_agent(agent_id: uuid.UUID, store: Store, member: CurrentMember) -> AgentSummary:
    """One agent with its model connection, instructions, tools and limits."""
    return service.summarize(await service.require_agent(store, member, agent_id))


@router.patch("/agents/{agent_id}", responses={**NOT_FOUND, **CONFLICT, **INVALID})
async def update_agent(
    agent_id: uuid.UUID,
    body: AgentUpdate,
    store: Store,
    connections: Connections,
    flows: Flows,
    member: CurrentMember,
) -> AgentSummary:
    """Changes the fields you send. Null clears the optional limits and the connection."""
    updated = await service.update_agent(store, connections, flows, member, agent_id, body)
    return service.summarize(updated)


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT, responses=NOT_FOUND)
async def delete_agent(agent_id: uuid.UUID, store: Store, member: CurrentMember) -> None:
    """Deletes the agent and all of its conversations."""
    await service.delete_agent(store, member, agent_id)


@router.post("/agents/{agent_id}/threads", status_code=status.HTTP_201_CREATED, responses=NOT_FOUND)
async def create_thread(agent_id: uuid.UUID, store: Store, member: CurrentMember) -> ThreadSummary:
    """Starts a conversation with the agent."""
    await service.require_agent(store, member, agent_id)
    return service.summarize_thread(await store.create_thread(member, agent_id))


@router.get("/agents/{agent_id}/threads", responses=NOT_FOUND)
async def list_threads(
    agent_id: uuid.UUID,
    store: Store,
    member: CurrentMember,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> ThreadList:
    """The workspace's conversations with the agent, most recently active first.

    Anyone in the workspace can read and continue a conversation by its id.
    """
    await service.require_agent(store, member, agent_id)
    threads = await store.list_threads(member, agent_id, limit)
    return ThreadList(items=[service.summarize_thread(t) for t in threads])


@router.get("/agents/{agent_id}/threads/{thread_id}", responses=NOT_FOUND)
async def get_thread(
    agent_id: uuid.UUID, thread_id: uuid.UUID, store: Store, member: CurrentMember
) -> ThreadDetail:
    """A conversation with all of its messages, oldest first."""
    thread = await service.require_thread(store, member, agent_id, thread_id)
    messages = await store.list_messages(thread.id)
    return ThreadDetail(
        thread=service.summarize_thread(thread), messages=[service.info(m) for m in messages]
    )


@router.delete(
    "/agents/{agent_id}/threads/{thread_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=NOT_FOUND,
)
async def delete_thread(
    agent_id: uuid.UUID, thread_id: uuid.UUID, store: Store, member: CurrentMember
) -> None:
    """Deletes a conversation and all of its messages. This cannot be undone."""
    if not await store.delete_thread(member, agent_id, thread_id):
        raise service.not_found("Thread")


def get_tracer_factory() -> service.TracerFactory:
    return lambda name: MlflowAgentObserver(get_settings(), name)


def turn_context(
    store: AgentStore,
    flows: FlowStore,
    member: Any,
    limits: Limits,
    load_secrets: SecretLoader,
    new_tracer: service.TracerFactory,
) -> service.TurnContext:
    outbound = outbound_policy(get_settings(), limits)
    return service.TurnContext(store, flows, member, limits, outbound, load_secrets, new_tracer)


@router.post(
    "/agents/{agent_id}/threads/{thread_id}/messages",
    responses={**NOT_FOUND, **CONFLICT, **INVALID, **TOO_MANY, **MODEL_FAILED},
    dependencies=[Depends(limit_runs)],
)
async def send_message(
    agent_id: uuid.UUID,
    thread_id: uuid.UUID,
    body: MessageRequest,
    store: Store,
    flows: Flows,
    member: CurrentMember,
    load_secrets: Annotated[SecretLoader, Depends(get_secret_loader)],
    new_tracer: Annotated[service.TracerFactory, Depends(get_tracer_factory)],
    slots: Annotated[RunSlots, Depends(get_run_slots)],
    limits: Annotated[Limits, Depends(get_limits)],
) -> TurnResponse:
    """Sends a message and waits for the answer.

    The agent may run its flows first. Nothing is stored if the turn fails: 422 `agent_not_ready`
    (no connection, model or usable flow), 422 `agent_stopped` (a limit was reached before an
    answer), 502 `model_failed` (the provider refused or could not be reached).
    """
    agent = await service.require_agent(store, member, agent_id)
    thread = await service.require_thread(store, member, agent_id, thread_id)
    ctx = turn_context(store, flows, member, limits, load_secrets, new_tracer)
    async with slots.hold(member.workspace_id):
        user, reply = await service.run_turn(ctx, agent, thread, body.content)
    return TurnResponse(user_message=service.info(user), reply=service.info(reply))


@router.get(
    "/agents/{agent_id}/threads/{thread_id}/messages/{message_id}/steps",
    responses={**NOT_FOUND, 503: {"model": ErrorResponse}},
)
async def get_message_steps(
    agent_id: uuid.UUID,
    thread_id: uuid.UUID,
    message_id: uuid.UUID,
    store: Store,
    member: CurrentMember,
    read: Annotated[TraceReader, Depends(get_trace_reader)],
) -> RunSteps:
    """How the agent answered a message: each model call and each flow it ran, with timings.

    `pending` while the trace is still being written. A message without a trace has no steps.
    """
    return await service.message_steps(store, member, agent_id, thread_id, message_id, read)


@router.post(
    "/agents/{agent_id}/invoke",
    response_class=StreamingResponse,
    response_model=None,
    responses={
        200: {
            "model": TurnResponse,
            "content": {"text/event-stream": {}},
            "description": "AG-UI events, or JSON when the request accepts only JSON",
        },
        **NOT_FOUND,
        **CONFLICT,
        **INVALID,
        **TOO_MANY,
        **MODEL_FAILED,
    },
    dependencies=[Depends(limit_runs)],
)
async def invoke_agent(
    agent_id: uuid.UUID,
    request: Request,
    store: Store,
    flows: Flows,
    member: CurrentMember,
    load_secrets: Annotated[SecretLoader, Depends(get_secret_loader)],
    new_tracer: Annotated[service.TracerFactory, Depends(get_tracer_factory)],
    slots: Annotated[RunSlots, Depends(get_run_slots)],
    limits: Annotated[Limits, Depends(get_limits)],
) -> StreamingResponse | JSONResponse:
    """Sends a message to the agent and returns its answer.

    The body is AG-UI's `RunAgentInput`. `threadId` is the id of one of your conversations with
    the agent, and only the last user message in `messages` is used: the server keeps the
    history. Send `Accept: application/json` to wait for the stored `user_message` and `reply`
    (errors as in the plain messages endpoint). Otherwise the answer streams as AG-UI events, the
    open agent-to-UI standard: `RUN_STARTED`, then text messages and tool calls as they happen,
    then a `message.stored` custom event holding the stored messages, then `RUN_FINISHED`, or
    `RUN_ERROR` instead.
    """
    try:
        run = RunAgentInput.model_validate(await request.json())
        thread_id = uuid.UUID(run.thread_id)
    except ValueError:
        raise ApiError(
            422, "invalid_run", "Send an AG-UI run input with the id of a conversation"
        ) from None
    agent = await service.require_agent(store, member, agent_id)
    thread = await service.require_thread(store, member, agent_id, thread_id)
    content = ag_ui.new_user_text(run)
    if content is None:
        raise ApiError(422, "no_message", "The run input has no user message")
    ctx = turn_context(store, flows, member, limits, load_secrets, new_tracer)
    accept = request.headers.get("accept") or ""

    if "application/json" in accept and "text/event-stream" not in accept:
        async with slots.hold(member.workspace_id):
            user, reply = await service.run_turn(ctx, agent, thread, content)
        done = TurnResponse(user_message=service.info(user), reply=service.info(reply))
        return JSONResponse(done.model_dump(mode="json"))

    encoder = EventEncoder(accept=accept)

    async def events() -> AsyncIterator[str]:
        async for event in ag_ui.run_events(ctx, agent, thread, content, slots):
            yield encoder.encode(event)

    return StreamingResponse(
        events(), media_type=encoder.get_content_type(), headers={"Cache-Control": "no-cache"}
    )
