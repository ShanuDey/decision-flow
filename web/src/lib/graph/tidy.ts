import dagre from "@dagrejs/dagre";

import type { FlowEdge, FlowNode } from "./convert";
import { NODE_SPECS } from "./nodes";
import type { Position } from "./types";

export interface Size {
  width: number;
  height: number;
}

const FALLBACK: Size = { width: 240, height: 80 };

// dagre returns node centers; React Flow positions by top-left.
export function tidy(
  nodes: FlowNode[],
  edges: FlowEdge[],
  sizes: Record<string, Size>,
): Record<string, Position> {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", ranksep: 80, nodesep: 40, marginx: 0, marginy: 0 });
  g.setDefaultEdgeLabel(() => ({}));

  for (const n of nodes) g.setNode(n.id, sizes[n.id] ?? FALLBACK);

  const known = new Set(nodes.map((n) => n.id));
  for (const e of edges) if (known.has(e.source) && known.has(e.target)) g.setEdge(e.source, e.target);

  // Top-to-bottom order of a branch node's targets follows its handle order.
  const constraints: { left: string; right: string }[] = [];
  for (const n of nodes) {
    const targets = NODE_SPECS[n.type].handles
      .map((h) => edges.find((e) => e.source === n.id && (e.sourceHandle ?? "") === h)?.target)
      .filter((t): t is string => !!t && known.has(t));
    for (let i = 1; i < targets.length; i++) {
      if (targets[i - 1] !== targets[i]) constraints.push({ left: targets[i - 1], right: targets[i] });
    }
  }

  dagre.layout(g, { constraints });

  const out: Record<string, Position> = {};
  for (const n of nodes) {
    const p = g.node(n.id);
    const size = sizes[n.id] ?? FALLBACK;
    out[n.id] = { x: Math.round(p.x - size.width / 2), y: Math.round(p.y - size.height / 2) };
  }
  return out;
}
