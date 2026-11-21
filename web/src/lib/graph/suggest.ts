import type { Contracts } from "./subflow";
import type { Graph, GraphNode } from "./types";

export interface Suggestion {
  // the full dotted path that replaces the token being typed
  insert: string;
  label: string;
  detail: string;
}

export interface Suggestions {
  from: number;
  items: Suggestion[];
}

const ROOTS: Suggestion[] = [
  { insert: "input.", label: "input", detail: "flow inputs" },
  { insert: "vars.", label: "vars", detail: "variables" },
  { insert: "nodes.", label: "nodes", detail: "outputs of earlier nodes" },
];

const SECRETS_ROOT: Suggestion = { insert: "secrets.", label: "secrets", detail: "saved secrets" };

const TOKEN = /[A-Za-z_]\w*(?:\.\w*)*$|\.?$/;

export function ancestors(graph: Graph, nodeId: string): Set<string> {
  const parents = new Map<string, string[]>();
  for (const e of graph.edges) parents.set(e.target, [...(parents.get(e.target) ?? []), e.source]);
  const seen = new Set<string>();
  const stack = [nodeId];
  while (stack.length) {
    for (const p of parents.get(stack.pop()!) ?? []) {
      if (!seen.has(p)) {
        seen.add(p);
        stack.push(p);
      }
    }
  }
  return seen;
}

export function outputKeys(
  node: GraphNode,
  graph: Graph,
  contracts: Contracts = {},
): { name: string; type: string }[] {
  switch (node.type) {
    case "start":
      return node.data.inputs.map((i) => ({ name: i.name, type: i.type }));
    case "assign": {
      const typeOf = new Map(graph.variables.map((v) => [v.name, v.type as string]));
      return node.data.assignments
        .filter((a) => a.variable)
        .map((a) => ({ name: a.variable, type: typeOf.get(a.variable) ?? "unknown" }));
    }
    case "condition":
      return [
        { name: "result", type: "boolean" },
        { name: "expression", type: "string" },
      ];
    case "http_request":
      return [
        { name: "status", type: "number" },
        { name: "ok", type: "boolean" },
        { name: "headers", type: "object" },
        { name: "body", type: "unknown" },
        { name: "duration_ms", type: "number" },
      ];
    case "prompt":
      return [
        { name: "text", type: "string" },
        { name: "model", type: "string" },
        { name: "finish_reason", type: "string" },
        { name: "usage", type: "object" },
      ];
    case "structured_output":
      return node.data.fields.filter((f) => f.name).map((f) => ({ name: f.name, type: f.type }));
    case "subflow":
      return contracts[node.data.flow_id]?.outputs ?? [];
    case "end":
      return [];
  }
}

function candidates(
  graph: Graph,
  nodeId: string,
  head: string[],
  secrets: string[] | undefined,
  contracts: Contracts,
): Suggestion[] {
  const [scope, id, output] = head;
  if (head.length === 0) return secrets ? [...ROOTS, SECRETS_ROOT] : ROOTS;
  if (head.length === 1 && scope === "secrets") {
    return (secrets ?? []).map((name) => ({ insert: `secrets.${name}`, label: name, detail: "secret" }));
  }
  if (head.length === 1 && scope === "input") {
    const start = graph.nodes.find((n) => n.type === "start");
    const inputs = start?.type === "start" ? start.data.inputs : [];
    return inputs.map((i) => ({
      insert: `input.${i.name}`,
      label: i.name,
      detail: `${i.type}${i.required ? " · required" : ""}`,
    }));
  }
  if (head.length === 1 && scope === "vars") {
    return graph.variables.map((v) => ({
      insert: `vars.${v.name}`,
      label: v.name,
      detail: v.type,
    }));
  }
  const upstream = ancestors(graph, nodeId);
  if (head.length === 1 && scope === "nodes") {
    return graph.nodes
      .filter((n) => upstream.has(n.id))
      .map((n) => ({ insert: `nodes.${n.id}.output.`, label: n.id, detail: `${n.name} · ${n.type}` }));
  }
  const node = graph.nodes.find((n) => n.id === id);
  if (scope !== "nodes" || !node || !upstream.has(node.id)) return [];
  if (head.length === 2) {
    return [{ insert: `nodes.${node.id}.output`, label: "output", detail: node.name }];
  }
  if (head.length === 3 && output === "output") {
    return outputKeys(node, graph, contracts).map((k) => ({
      insert: `nodes.${node.id}.output.${k.name}`,
      label: k.name,
      detail: k.type,
    }));
  }
  return [];
}

function insideString(text: string): boolean {
  let quote = "";
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quote) {
      if (c === "\\") i++;
      else if (c === quote) quote = "";
    } else if (c === '"' || c === "'") quote = c;
  }
  return quote !== "";
}

// Offers the path ending at `cursor` (`from` is where it starts); `secrets` only where accepted.
export function suggest(
  graph: Graph,
  nodeId: string,
  text: string,
  cursor: number,
  secrets?: string[],
  contracts: Contracts = {},
): Suggestions {
  const before = text.slice(0, cursor);
  if (insideString(before)) return { from: cursor, items: [] };
  const token = before.match(TOKEN)?.[0] ?? "";
  const from = cursor - token.length;
  const prev = before[from - 1];
  if (token.startsWith(".") || (prev && /[\w.]/.test(prev))) return { from, items: [] };
  const parts = token.split(".");
  const partial = parts[parts.length - 1].toLowerCase();
  const items = candidates(graph, nodeId, parts.slice(0, -1), secrets, contracts).filter(
    (c) => c.label.toLowerCase().startsWith(partial) && c.insert !== token,
  );
  return { from, items };
}
