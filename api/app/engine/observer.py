"""Hooks the runtime calls around every node. Tracing (MLflow) and SSE events plug in here."""

from typing import Literal, Protocol

NodeStatus = Literal["ok", "failed"]


class NodeError(Exception):
    def __init__(self, node_id: str, message: str) -> None:
        super().__init__(f"{node_id}: {message}")
        self.node_id = node_id
        self.message = message


class Observer(Protocol):
    async def node_started(self, node_id: str) -> None: ...

    async def node_finished(
        self, node_id: str, status: NodeStatus, duration_ms: int, error: str | None
    ) -> None: ...


class NullObserver:
    async def node_started(self, node_id: str) -> None:
        return None

    async def node_finished(
        self, node_id: str, status: NodeStatus, duration_ms: int, error: str | None
    ) -> None:
        return None
