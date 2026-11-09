"""Graph JSON to LangGraph. One of two modules allowed to import langgraph (with runtime)."""

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.engine.graph import EndNode, Graph, Node, StartNode, Variable
from app.engine.inputs import InputValidationError, check_value, validate_input
from app.engine.observer import NodeError, NullObserver
from app.engine.templates import render

Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def _merge(left: dict, right: dict) -> dict:
    return {**left, **right}


class FlowState(TypedDict):
    input: dict[str, Any]
    vars: dict[str, Any]
    nodes: Annotated[dict[str, Any], _merge]
    # underscore prefix: node ids can never collide with it
    _output: dict[str, Any]


@dataclass(frozen=True)
class CompiledFlow:
    graph: Any
    start: StartNode
    variables: list[Variable]


def compile_graph(graph: Graph) -> CompiledFlow:
    """Expects a graph that passed `parse_graph`."""
    builder = StateGraph(FlowState)
    start: StartNode | None = None
    for node in graph.nodes:
        builder.add_node(node.id, _wrap(node.id, _handler_for(node)))
        if isinstance(node, StartNode):
            start = node
        if isinstance(node, EndNode):
            builder.add_edge(node.id, END)
    assert start is not None
    builder.add_edge(START, start.id)
    for edge in graph.edges:
        builder.add_edge(edge.source, edge.target)
    return CompiledFlow(builder.compile(), start, graph.variables)


def _handler_for(node: Node) -> Handler:
    if isinstance(node, StartNode):

        async def start(state: dict[str, Any]) -> dict[str, Any]:
            # run_flow already validated; repeating makes direct graph callers (Studio) get defaults
            try:
                inputs = validate_input(node.data.inputs, state["input"])
            except InputValidationError as exc:
                raise ValueError(str(exc)) from exc
            return {"input": inputs, "nodes": {node.id: {"output": inputs}}}

        return start

    async def end(state: dict[str, Any]) -> dict[str, Any]:
        scopes = {"input": state["input"], "vars": state.get("vars", {})}
        output: dict[str, Any] = {}
        for out in node.data.outputs:
            try:
                output[out.name] = check_value(out, render(out.value, scopes))
            except ValueError as exc:
                raise ValueError(f"output '{out.name}': {exc}") from exc
        return {"_output": output, "nodes": {node.id: {"output": output}}}

    return end


def _wrap(node_id: str, handler: Handler) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Central per-node hook: timing, observer events, errors tagged with the node id."""

    async def run(state: FlowState, config: RunnableConfig) -> dict[str, Any]:
        observer = config.get("configurable", {}).get("observer") or NullObserver()
        await observer.node_started(node_id)
        started = time.perf_counter()
        try:
            update = await handler(state)  # type: ignore[arg-type]
        except Exception as exc:
            ms = int((time.perf_counter() - started) * 1000)
            await observer.node_finished(node_id, "failed", ms, str(exc))
            raise NodeError(node_id, str(exc)) from exc
        await observer.node_finished(
            node_id, "ok", int((time.perf_counter() - started) * 1000), None
        )
        return update

    return run
