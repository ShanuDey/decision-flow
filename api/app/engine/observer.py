"""Hooks the runtime calls around a run and every node. Tracing (MLflow) and SSE plug in here."""

from typing import Any, Literal, Protocol

from app.engine.base import FrozenBaseModel

NodeStatus = Literal["ok", "failed"]
RunStatus = Literal["succeeded", "failed"]


class NodeInfo(FrozenBaseModel):
    id: str
    type: str
    name: str
    # Key of the subflow node this node runs under; None at the top level.
    parent: str | None = None

    @property
    def key(self) -> str:
        return f"{self.parent}>{self.id}" if self.parent else self.id


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


class ScopedObserver:
    """Reports a subflow's nodes under the subflow node; the run itself belongs to the parent."""

    def __init__(self, inner: Observer, scope: str) -> None:
        self._inner = inner
        self._scope = scope

    def _stamp(self, node: NodeInfo) -> NodeInfo:
        # a deeper subflow stamped its own nodes already
        return node if node.parent else node.model_copy(update={"parent": self._scope})

    async def run_started(self, inputs: dict[str, Any]) -> None:
        return None

    async def node_started(self, node: NodeInfo, inputs: dict[str, Any]) -> None:
        await self._inner.node_started(self._stamp(node), inputs)

    async def node_finished(
        self,
        node: NodeInfo,
        status: NodeStatus,
        duration_ms: int,
        error: str | None,
        outputs: Any = None,
    ) -> None:
        await self._inner.node_finished(self._stamp(node), status, duration_ms, error, outputs)

    async def run_finished(
        self, status: RunStatus, error: str | None, outputs: dict[str, Any] | None = None
    ) -> None:
        return None
