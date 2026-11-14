import { ancestors, outputKeys } from "./suggest";
import type { Graph } from "./types";

export interface DataItem {
  label: string;
  path: string;
  detail: string;
}

export interface DataSection {
  title: string;
  items: DataItem[];
}

// What a node's expressions can read: flow inputs, variables and outputs of earlier nodes.
export function availableData(graph: Graph, nodeId: string): DataSection[] {
  const start = graph.nodes.find((n) => n.type === "start");
  const inputs = start?.type === "start" ? start.data.inputs : [];
  const upstream = ancestors(graph, nodeId);
  const sections: DataSection[] = [
    {
      title: "input",
      items: inputs
        .filter((i) => i.name)
        .map((i) => ({ label: i.name, path: `input.${i.name}`, detail: i.type })),
    },
    {
      title: "vars",
      items: graph.variables
        .filter((v) => v.name)
        .map((v) => ({ label: v.name, path: `vars.${v.name}`, detail: v.type })),
    },
    {
      title: "nodes",
      items: graph.nodes
        .filter((n) => upstream.has(n.id))
        .flatMap((n) =>
          outputKeys(n, graph).map((k) => ({
            label: `${n.id}.${k.name}`,
            path: `nodes.${n.id}.output.${k.name}`,
            detail: k.type,
          })),
        ),
    },
  ];
  return sections.filter((s) => s.items.length > 0);
}

const sample = (type: string): unknown =>
  type === "number" ? 0 : type === "boolean" ? false : type === "array" ? [] : type === "object" ? {} : "";

// Typed placeholder values for everything the node can read, nested like the real scope.
export function sampleScope(sections: DataSection[]): string {
  const scope: Record<string, unknown> = {};
  for (const item of sections.flatMap((s) => s.items)) {
    const keys = item.path.split(".");
    let at = scope;
    for (const key of keys.slice(0, -1)) {
      at = (at[key] ??= {}) as Record<string, unknown>;
    }
    at[keys[keys.length - 1]] = sample(item.detail);
  }
  return JSON.stringify(scope, null, 2);
}
