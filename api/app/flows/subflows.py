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


def called_flows(raw: Any) -> list[tuple[str, str, str]]:
    """(node id, flow id, field) for each flow a subflow or agent node of a draft may run.

    The draft may not even be valid, so it is read as plain JSON.
    """
    nodes = raw.get("nodes") if isinstance(raw, dict) else None
    found: list[tuple[str, str, str]] = []
    for node in nodes if isinstance(nodes, list) else []:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str):
            continue
        data = node.get("data")
        data = data if isinstance(data, dict) else {}
        if node.get("type") == "subflow":
            refs = [("data.flow_id", data.get("flow_id"))]
        elif node.get("type") == "agent":
            tools = data.get("tools")
            refs = [
                (f"data.tools.{i}.flow_id", t.get("flow_id"))
                for i, t in enumerate(tools if isinstance(tools, list) else [])
                if isinstance(t, dict)
            ]
        else:
            continue
        found += [
            (node["id"], flow_id, field) for field, flow_id in refs if isinstance(flow_id, str)
        ]
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
        pending = [flow_id for _, flow_id, _ in called_flows(raw)]
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
        contracts = await self.contracts(graph.model_dump(mode="json"))
        return {name for c in contracts.values() for name in c.secret_names}

    async def connection_ids(self, graph: Graph) -> set[str]:
        """Connections the flows it calls use, loaded with the run's own."""
        contracts = await self.contracts(graph.model_dump(mode="json"))
        return {cid for c in contracts.values() for cid in c.connection_ids}


def loop_issues(flow_id: uuid.UUID, raw: Any, contracts: dict[str, FlowContract]) -> list[Issue]:
    """A flow that can reach itself through its calls would never stop calling."""
    own = str(flow_id)
    issues: list[Issue] = []
    for node_id, target, field in called_flows(raw):
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
                        field=field,
                    )
                )
                break
            if current in seen or current not in contracts:
                continue
            seen.add(current)
            pending.extend(contracts[current].calls)
    return issues
