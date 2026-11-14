"""Graph validation: schema, structure, references. Per-type rules live on the node types."""

import re
from collections import defaultdict, deque
from typing import Any

from pydantic import ValidationError

from app.engine import expressions
from app.engine.graph import Edge, Graph
from app.engine.inputs import check_value
from app.engine.issues import Issue
from app.engine.nodes import NODE_TYPES, NodeContext, NodeModel, StartNode
from app.engine.templates import Ref, TemplateError, references

RESERVED_IDS = {"input", "vars", "nodes", "secrets", "env", "run"}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _issue(code: str, message: str, node_id: str | None = None, field: str | None = None) -> Issue:
    return Issue(code=code, message=message, node_id=node_id, field=field)


def check_size(raw: Any, max_nodes: int, max_edges: int) -> list[Issue]:
    """0 means no cap. Runs on the raw JSON so an oversized graph is refused before parsing."""
    if not isinstance(raw, dict):
        return []
    issues: list[Issue] = []
    for key, cap, code in (
        ("nodes", max_nodes, "too_many_nodes"),
        ("edges", max_edges, "too_many_edges"),
    ):
        items = raw.get(key)
        if cap and isinstance(items, list) and len(items) > cap:
            issues.append(
                _issue(code, f"flow has {len(items)} {key}; the limit is {cap}", None, key)
            )
    return issues


def parse_graph(
    raw: Any, max_nodes: int = 0, max_edges: int = 0
) -> tuple[Graph | None, list[Issue]]:
    """Stages 0 (size), 1 (schema), 2 (structure), 3 (settings); each needs the last to pass."""
    if size_issues := check_size(raw, max_nodes, max_edges):
        return None, size_issues
    try:
        graph = Graph.model_validate(raw)
    except ValidationError as exc:
        return None, [_schema_issue(raw, err) for err in exc.errors()]
    issues = check_structure(graph) or check_settings(graph)
    return (None if issues else graph), issues


def _schema_issue(raw: Any, err: Any) -> Issue:
    loc = err["loc"]
    node_id = None
    if len(loc) > 1 and loc[0] == "nodes" and isinstance(loc[1], int):
        try:
            node_id = raw["nodes"][loc[1]].get("id")
        except (KeyError, IndexError, AttributeError, TypeError):
            pass
    return _issue("schema", err["msg"], node_id, ".".join(str(p) for p in loc))


def check_settings(graph: Graph) -> list[Issue]:
    issues: list[Issue] = []
    ctx = NodeContext(variables=graph.variables)
    inputs = {f.name for n in graph.nodes if isinstance(n, StartNode) for f in n.data.inputs}
    variables = {v.name for v in graph.variables}
    ids = {n.id for n in graph.nodes}
    for node in graph.nodes:
        issues.extend(node.check(ctx))
        for field, template in node.templates().items():
            try:
                refs = references(template)
            except TemplateError as exc:
                issues.append(_issue("unsupported_expression", str(exc), node.id, field))
                continue
            for ref in refs:
                known = inputs if ref.scope == "input" else variables
                if ref.path[0] not in known:
                    issues.append(
                        _issue("unknown_reference", f"{ref} is not declared", node.id, field)
                    )
        exprs = node.expressions()
        upstream = _ancestors(graph, node.id) if exprs else set()
        for field, source in exprs.items():
            try:
                refs = expressions.references(expressions.compile(source))
            except expressions.ExpressionError as exc:
                issues.append(_issue("invalid_expression", str(exc), node.id, field))
                continue
            for ref in refs:
                problem = _reference_problem(ref, inputs, variables, ids, upstream)
                if problem:
                    issues.append(_issue(*problem, node.id, field))
    return issues


def _reference_problem(
    ref: Ref, inputs: set[str], variables: set[str], ids: set[str], upstream: set[str]
) -> tuple[str, str] | None:
    if not ref.path:
        return None
    head = ref.path[0]
    if ref.scope == "nodes" and head in ids and head not in upstream:
        return "not_upstream", f"{ref} reads node '{head}', which does not run before this node"
    known = {"input": inputs, "vars": variables, "nodes": ids}[ref.scope]
    if head not in known:
        return "unknown_reference", f"{ref} is not declared"
    if ref.scope == "nodes" and len(ref.path) > 1 and ref.path[1] != "output":
        return "unknown_reference", f"{ref}: a node only has 'output'"
    return None


def _ancestors(graph: Graph, node_id: str) -> set[str]:
    parents: dict[str, list[str]] = defaultdict(list)
    for e in graph.edges:
        parents[e.target].append(e.source)
    seen: set[str] = set()
    stack = [node_id]
    while stack:
        for parent in parents[stack.pop()]:
            if parent not in seen:
                seen.add(parent)
                stack.append(parent)
    return seen


def _bounds(cls: type[NodeModel]) -> str:
    if cls.max_count == cls.min_count:
        return f"exactly {cls.min_count}"
    if cls.max_count is None:
        return f"at least {cls.min_count}"
    return f"{cls.min_count} to {cls.max_count}"


def check_structure(graph: Graph) -> list[Issue]:
    issues: list[Issue] = []
    nodes = {n.id: n for n in graph.nodes}

    for cls in NODE_TYPES:
        count = sum(isinstance(n, cls) for n in graph.nodes)
        if count < cls.min_count or (cls.max_count is not None and count > cls.max_count):
            issues.append(
                _issue(
                    "node_count",
                    f"expected {_bounds(cls)} '{cls.type_name()}' node(s), found {count}",
                )
            )

    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    for n in graph.nodes:
        if n.id in seen_ids:
            issues.append(_issue("duplicate_id", f"duplicate node id '{n.id}'", n.id, "id"))
        seen_ids.add(n.id)
        if n.id in RESERVED_IDS:
            issues.append(_issue("reserved_id", f"'{n.id}' is a reserved word", n.id, "id"))
        elif not ID_PATTERN.match(n.id):
            issues.append(
                _issue("bad_id", f"id '{n.id}' must match {ID_PATTERN.pattern}", n.id, "id")
            )
        name = n.name or n.type
        if name in seen_names:
            issues.append(_issue("duplicate_name", f"duplicate node name '{name}'", n.id, "name"))
        seen_names.add(name)

    var_names: set[str] = set()
    for v in graph.variables:
        if v.name in var_names:
            issues.append(
                _issue("duplicate_variable", f"duplicate variable '{v.name}'", None, "variables")
            )
        var_names.add(v.name)
        if not NAME_PATTERN.match(v.name):
            issues.append(
                _issue(
                    "invalid_variable_name",
                    f"variable '{v.name}' must match {NAME_PATTERN.pattern}",
                    None,
                    "variables",
                )
            )
        if v.initial is not None:
            try:
                check_value(v, v.initial)
            except ValueError as exc:
                issues.append(
                    _issue(
                        "invalid_initial",
                        f"variable '{v.name}' initial value: {exc}",
                        None,
                        "variables",
                    )
                )

    out: dict[str, list[str]] = defaultdict(list)
    out_edges: dict[str, list[Edge]] = defaultdict(list)
    incoming: dict[str, int] = defaultdict(int)
    edge_ok = True
    for e in graph.edges:
        for end_name, node_id in (("source", e.source), ("target", e.target)):
            if node_id not in nodes:
                edge_ok = False
                issues.append(
                    _issue(
                        "dangling_edge",
                        f"edge '{e.id}' {end_name} '{node_id}' not found",
                        None,
                        f"edges.{e.id}.{end_name}",
                    )
                )
        if e.source in nodes and e.target in nodes:
            out[e.source].append(e.target)
            out_edges[e.source].append(e)
            incoming[e.target] += 1
    if not edge_ok:
        return issues  # later checks assume every edge resolves

    for n in graph.nodes:
        if not n.accepts_incoming and incoming[n.id]:
            issues.append(
                _issue("incoming_not_allowed", f"'{n.type}' node cannot have incoming edges", n.id)
            )
        if not n.accepts_outgoing and out[n.id]:
            issues.append(
                _issue("outgoing_not_allowed", f"'{n.type}' node cannot have outgoing edges", n.id)
            )
        if n.handles:
            issues.extend(_check_branches(n, out_edges[n.id]))
            continue
        if n.accepts_outgoing and not out[n.id]:
            issues.append(_issue("no_outgoing_edge", f"node '{n.id}' has no outgoing edge", n.id))
        # Temporary: fan-out needs Merge and `vars` reducers (slice 3); lift this check there.
        if len(out[n.id]) > 1:
            issues.append(
                _issue(
                    "parallel_not_supported",
                    f"node '{n.id}' has {len(out[n.id])} outgoing edges; parallel branches "
                    "are not supported yet",
                    n.id,
                )
            )

    entries = [n for n in graph.nodes if not n.accepts_incoming]
    if _has_cycle(nodes, out, incoming):
        issues.append(_issue("cycle", "flow contains a cycle; only DAGs are supported"))
    elif len(entries) == 1:
        reachable = _reachable(entries[0].id, out)
        for n in graph.nodes:
            if n.id not in reachable:
                issues.append(
                    _issue("unreachable", f"node '{n.id}' is not reachable from start", n.id)
                )

    for cls in NODE_TYPES:
        group = [n for n in graph.nodes if isinstance(n, cls)]
        if group:
            issues.extend(cls.check_group(group))
    return issues


def _check_branches(node: NodeModel, edges: list[Edge]) -> list[Issue]:
    issues: list[Issue] = []
    for e in edges:
        if e.sourceHandle not in node.handles:
            issues.append(
                _issue(
                    "invalid_handle",
                    f"edge '{e.id}' leaves '{node.id}' from {e.sourceHandle!r}; "
                    f"expected one of {list(node.handles)}",
                    node.id,
                    f"edges.{e.id}.sourceHandle",
                )
            )
    for handle in node.handles:
        count = sum(e.sourceHandle == handle for e in edges)
        if count == 0:
            issues.append(
                _issue("missing_branch", f"'{node.id}' has no '{handle}' edge", node.id, handle)
            )
        elif count > 1:
            issues.append(
                _issue(
                    "parallel_not_supported",
                    f"'{node.id}' has {count} '{handle}' edges; parallel branches "
                    "are not supported yet",
                    node.id,
                    handle,
                )
            )
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
