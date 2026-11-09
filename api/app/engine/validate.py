"""Graph validation, stages 1 and 2 of graph-schema.md section 5. Pure functions."""

import re
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.engine.graph import EndNode, Graph, StartNode
from app.engine.templates import TemplateError, references

RESERVED_IDS = {"input", "vars", "nodes", "secrets", "env", "run"}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    node_id: str | None = None
    field: str | None = None


def parse_graph(raw: Any) -> tuple[Graph | None, list[Issue]]:
    """Stages 1 (schema), 2 (structure), 3 (references); each runs only if the last passed."""
    try:
        graph = Graph.model_validate(raw)
    except ValidationError as exc:
        return None, [_schema_issue(raw, err) for err in exc.errors()]
    issues = check_structure(graph) or check_references(graph)
    return (None if issues else graph), issues


def check_references(graph: Graph) -> list[Issue]:
    issues: list[Issue] = []
    inputs = {f.name for n in graph.nodes if isinstance(n, StartNode) for f in n.data.inputs}
    variables = {v.name for v in graph.variables}
    for node in graph.nodes:
        if not isinstance(node, EndNode):
            continue
        for out in node.data.outputs:
            field = f"data.outputs.{out.name}.value"
            try:
                refs = references(out.value)
            except TemplateError as exc:
                issues.append(Issue("unsupported_expression", str(exc), node.id, field))
                continue
            for ref in refs:
                known = inputs if ref.scope == "input" else variables
                if ref.path[0] not in known:
                    issues.append(
                        Issue("unknown_reference", f"{ref} is not declared", node.id, field)
                    )
    return issues


def _schema_issue(raw: Any, err: Any) -> Issue:
    loc = err["loc"]
    node_id = None
    if len(loc) > 1 and loc[0] == "nodes" and isinstance(loc[1], int):
        try:
            node_id = raw["nodes"][loc[1]].get("id")
        except (KeyError, IndexError, AttributeError, TypeError):
            pass
    return Issue("schema", err["msg"], node_id, ".".join(str(p) for p in loc))


def check_structure(graph: Graph) -> list[Issue]:
    issues: list[Issue] = []
    nodes = {n.id: n for n in graph.nodes}

    starts = [n for n in graph.nodes if isinstance(n, StartNode)]
    ends = [n for n in graph.nodes if isinstance(n, EndNode)]
    if len(starts) != 1:
        issues.append(Issue("start_count", f"expected exactly one start node, found {len(starts)}"))
    if not ends:
        issues.append(Issue("end_missing", "flow needs at least one end node"))

    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    for n in graph.nodes:
        if n.id in seen_ids:
            issues.append(Issue("duplicate_id", f"duplicate node id '{n.id}'", n.id, "id"))
        seen_ids.add(n.id)
        if n.id in RESERVED_IDS:
            issues.append(Issue("reserved_id", f"'{n.id}' is a reserved word", n.id, "id"))
        elif not ID_PATTERN.match(n.id):
            issues.append(
                Issue("bad_id", f"id '{n.id}' must match {ID_PATTERN.pattern}", n.id, "id")
            )
        name = n.name or n.type
        if name in seen_names:
            issues.append(Issue("duplicate_name", f"duplicate node name '{name}'", n.id, "name"))
        seen_names.add(name)

    var_names: set[str] = set()
    for v in graph.variables:
        if v.name in var_names:
            issues.append(
                Issue("duplicate_variable", f"duplicate variable '{v.name}'", None, "variables")
            )
        var_names.add(v.name)

    out: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, int] = defaultdict(int)
    edge_ok = True
    for e in graph.edges:
        for end_name, node_id in (("source", e.source), ("target", e.target)):
            if node_id not in nodes:
                edge_ok = False
                issues.append(
                    Issue(
                        "dangling_edge",
                        f"edge '{e.id}' {end_name} '{node_id}' not found",
                        None,
                        f"edges.{e.id}.{end_name}",
                    )
                )
        if e.source in nodes and e.target in nodes:
            out[e.source].append(e.target)
            incoming[e.target] += 1
    if not edge_ok:
        return issues  # later checks assume every edge resolves

    for n in graph.nodes:
        if isinstance(n, StartNode) and incoming[n.id]:
            issues.append(
                Issue("start_has_incoming", "start node cannot have incoming edges", n.id)
            )
        if isinstance(n, EndNode) and out[n.id]:
            issues.append(Issue("end_has_outgoing", "end node cannot have outgoing edges", n.id))
        if not isinstance(n, EndNode) and not out[n.id]:
            issues.append(Issue("no_outgoing_edge", f"node '{n.id}' has no outgoing edge", n.id))

    if _has_cycle(nodes, out, incoming):
        issues.append(Issue("cycle", "flow contains a cycle; only DAGs are supported"))
    elif len(starts) == 1:
        reachable = _reachable(starts[0].id, out)
        for n in graph.nodes:
            if n.id not in reachable:
                issues.append(
                    Issue("unreachable", f"node '{n.id}' is not reachable from start", n.id)
                )

    shapes = {tuple((o.name, o.type) for o in e.data.outputs) for e in ends}
    if len(shapes) > 1:
        issues.append(Issue("end_outputs_differ", "all end nodes must declare the same outputs"))
    return issues


def _has_cycle(nodes: dict, out: dict[str, list[str]], incoming: dict[str, int]) -> bool:
    indeg = {nid: incoming[nid] for nid in nodes}
    queue = deque(nid for nid, d in indeg.items() if d == 0)
    visited = 0
    while queue:
        nid = queue.popleft()
        visited += 1
        for nxt in out[nid]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    return visited != len(nodes)


def _reachable(start: str, out: dict[str, list[str]]) -> set[str]:
    seen, stack = {start}, [start]
    while stack:
        for nxt in out[stack.pop()]:
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen
