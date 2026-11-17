"""Lets a flow call other published flows: loads them, and checks the calls for loops."""

import uuid
from typing import Any

from pydantic import ValidationError

from app.engine.contracts import contract_of
from app.engine.graph import Graph
from app.engine.issues import Issue
from app.engine.subflow import FlowContract, SubflowAccess
from app.engine.validate import parse_graph
from app.flows.store import FlowStore
from app.limits import Limits
from app.security.ssrf import OutboundPolicy
from app.workspaces.schemas import Member


def called_flows(raw: Any) -> dict[str, str]:
    """Node id -> flow id for each subflow node in a draft that may not even be valid."""
    nodes = raw.get("nodes") if isinstance(raw, dict) else None
    found: dict[str, str] = {}
    for node in nodes if isinstance(nodes, list) else []:
        if not isinstance(node, dict) or node.get("type") != "subflow":
            continue
        data = node.get("data")
        flow_id = data.get("flow_id") if isinstance(data, dict) else None
        if isinstance(flow_id, str) and isinstance(node.get("id"), str):
            found[node["id"]] = flow_id
    return found


class SubflowSource:
    """The published flows one member can call. A flow is read once per source."""

    def __init__(
        self,
        store: FlowStore,
        member: Member,
        limits: Limits,
        outbound: OutboundPolicy | None = None,
    ) -> None:
        self._store = store
        self._member = member
        self._limits = limits
        self._outbound = outbound
        self._graphs: dict[str, Graph | None] = {}

    @property
    def access(self) -> SubflowAccess:
        return SubflowAccess(load=self.load, max_depth=self._limits.max_subflow_depth)

    async def _published(self, flow_id: str) -> Graph | None:
        """None when the flow is missing, in another workspace, or not published."""
        if flow_id not in self._graphs:
            self._graphs[flow_id] = await self._read(flow_id)
        return self._graphs[flow_id]

    async def _read(self, flow_id: str) -> Graph | None:
        try:
            parsed = uuid.UUID(flow_id)
        except ValueError:
            return None
        flow = await self._store.get_flow(self._member, parsed)
        if flow is None or flow.published_version is None:
            return None
        version = await self._store.get_version(self._member, parsed, flow.published_version)
        if version is None:
            return None
        try:
            return Graph.model_validate(version.graph)
        except ValidationError:
            return None

    async def load(self, flow_id: str) -> Graph:
        """The latest published version, ready to compile; ValueError says why it cannot be."""
        graph = await self._published(flow_id)
        if graph is None:
            raise ValueError("the flow is missing, or has no published version")
        checked, issues = parse_graph(
            graph.model_dump(mode="json"),
            self._limits.max_nodes,
            self._limits.max_edges,
            self._limits.disabled_node_types,
            self._outbound,
        )
        if checked is None:
            raise ValueError(f"the flow is no longer valid: {issues[0].message}")
        return checked

    async def contracts(self, raw: Any) -> dict[str, FlowContract]:
        """Every flow the draft calls, directly or through others; unavailable ones are absent."""
        found: dict[str, FlowContract] = {}
        pending = list(called_flows(raw).values())
        while pending:
            flow_id = pending.pop()
            if flow_id in found:
                continue
            graph = await self._published(flow_id)
            if graph is None:
                continue
            found[flow_id] = contract_of(graph)
            pending.extend(found[flow_id].calls)
        return found

    async def secret_names(self, graph: Graph) -> set[str]:
        """Secrets the flows it calls need, so a run can load them with its own."""
        names: set[str] = set()
        contracts = await self.contracts(graph.model_dump(mode="json"))
        for contract in contracts.values():
            names.update(contract.secret_names)
        return names


def loop_issues(flow_id: uuid.UUID, raw: Any, contracts: dict[str, FlowContract]) -> list[Issue]:
    """A flow that can reach itself through its calls would never stop calling."""
    own = str(flow_id)
    issues: list[Issue] = []
    for node_id, target in called_flows(raw).items():
        seen: set[str] = set()
        pending = [target]
        while pending:
            current = pending.pop()
            if current == own:
                issues.append(
                    Issue(
                        code="subflow_loop",
                        message="this flow calls itself, directly or through other flows",
                        node_id=node_id,
                        field="data.flow_id",
                    )
                )
                break
            if current in seen or current not in contracts:
                continue
            seen.add(current)
            pending.extend(contracts[current].calls)
    return issues
