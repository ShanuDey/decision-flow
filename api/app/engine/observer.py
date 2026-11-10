"""Hooks the runtime calls around a run and every node. Tracing (MLflow) and SSE plug in here."""

from typing import Any, Literal, Protocol

from app.engine.base import FrozenBaseModel

NodeStatus = Literal["ok", "failed"]
RunStatus = Literal["succeeded", "failed"]


class NodeInfo(FrozenBaseModel):
    id: str
    type: str
    name: str


class NodeError(Exception):
    def __init__(self, node_id: str, message: str) -> None:
        super().__init__(f"{node_id}: {message}")
        self.node_id = node_id
        self.message = message


class Observer(Protocol):
    async def run_started(self, inputs: dict[str, Any]) -> None: ...

    async def node_started(self, node: NodeInfo, inputs: dict[str, Any]) -> None: ...

    async def node_finished(
        self,
        node: NodeInfo,
        status: NodeStatus,
        duration_ms: int,
        error: str | None,
        outputs: Any = None,
    ) -> None: ...

    async def run_finished(
        self, status: RunStatus, error: str | None, outputs: dict[str, Any] | None = None
    ) -> None: ...


class NullObserver:
    async def run_started(self, inputs: dict[str, Any]) -> None:
        return None

    async def node_started(self, node: NodeInfo, inputs: dict[str, Any]) -> None:
        return None

    async def node_finished(
        self,
        node: NodeInfo,
        status: NodeStatus,
        duration_ms: int,
        error: str | None,
        outputs: Any = None,
    ) -> None:
        return None

    async def run_finished(
        self, status: RunStatus, error: str | None, outputs: dict[str, Any] | None = None
    ) -> None:
        return None
