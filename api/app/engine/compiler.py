"""Graph JSON to LangGraph. One of two modules allowed to import langgraph (with runtime)."""

import time
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from pydantic import create_model

from app.engine.base import FrozenBaseModel
from app.engine.graph import Graph
from app.engine.nodes import NodeContext, NodeModel, StartNode
from app.engine.observer import NodeError, NodeInfo, NullObserver


def _merge(left: dict, right: dict) -> dict:
    return {**left, **right}


def _replace(_: dict, new: dict) -> dict:
    # a reducer, so several End nodes can clear `input` in the same step
    return new


class FlowState(TypedDict):
    input: Annotated[dict[str, Any], _replace]
    vars: dict[str, Any]
    nodes: Annotated[dict[str, Any], _merge]
    # underscore prefix: node ids can never collide with it
    _output: dict[str, Any]


class CompiledFlow(FrozenBaseModel):
    graph: Any
    start: StartNode


def compile_graph(graph: Graph, checkpointer: Any = None) -> CompiledFlow:
    """Expects a graph that passed `parse_graph`. A checkpointer makes runs resumable by thread."""
    start = next(n for n in graph.nodes if isinstance(n, StartNode))
    ctx = NodeContext(variables=graph.variables)
    # input_schema: LangGraph accepts only the keys it names, so the run is seeded with `input`
    # alone; Start sets up `vars`.
    builder = StateGraph(
        FlowState, input_schema=create_model("FlowInput", input=(start.input_model(), ...))
    )
    for node in graph.nodes:
        builder.add_node(node.id, _wrap(node, ctx))
        if not node.accepts_outgoing:
            builder.add_edge(node.id, END)
    builder.add_edge(START, start.id)
    for edge in graph.edges:
        builder.add_edge(edge.source, edge.target)
    return CompiledFlow(graph=builder.compile(checkpointer=checkpointer), start=start)


def _wrap(node: NodeModel, ctx: NodeContext) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Central per-node hook: timing, observer events, errors tagged with the node id."""
    info = NodeInfo(id=node.id, type=node.type, name=node.name or node.type)

    async def run(state: FlowState, config: RunnableConfig) -> dict[str, Any]:
        observer = config.get("configurable", {}).get("observer") or NullObserver()
        # what a node can read: the scopes expressions see (nodes grows as the run proceeds)
        await observer.node_started(info, {k: state.get(k) for k in ("input", "vars", "nodes")})
        started = time.perf_counter()
        try:
            update = await node.run(state, ctx)  # type: ignore[arg-type]
        except Exception as exc:
            ms = int((time.perf_counter() - started) * 1000)
            await observer.node_finished(info, "failed", ms, str(exc))
            raise NodeError(info.id, str(exc)) from exc
        ms = int((time.perf_counter() - started) * 1000)
        output = update.get("nodes", {}).get(info.id, {}).get("output")
        await observer.node_finished(info, "ok", ms, None, output)
        return update

    return run
