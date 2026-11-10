import type { Edge, Node } from "@xyflow/react";

import type { Graph, GraphEdge, GraphNode, NodeData, NodeType, Variable } from "./types";

export type FlowNodeData = { name: string; config: NodeData };
export type FlowNode = Node<FlowNodeData, NodeType>;
export type FlowEdge = Edge;

export interface EditorGraph {
  nodes: FlowNode[];
  edges: FlowEdge[];
  variables: Variable[];
}

export function toReactFlow(graph: Graph): EditorGraph {
  return {
    variables: graph.variables,
    nodes: graph.nodes.map((n) => ({
      id: n.id,
      type: n.type,
      position: n.position,
      data: { name: n.name, config: n.data },
    })),
    edges: graph.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle,
    })),
  };
}

export function fromReactFlow({ nodes, edges, variables }: EditorGraph): Graph {
  return {
    schema_version: 1,
    variables,
    nodes: nodes.map(
      (n) =>
        ({
          id: n.id,
          type: n.type as NodeType,
          name: n.data.name,
          position: { x: n.position.x, y: n.position.y },
          data: n.data.config,
        }) as GraphNode,
    ),
    edges: edges.map(
      (e): GraphEdge => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle ?? null,
      }),
    ),
  };
}

// The draft arrives as untyped JSON; accept it only if it has the top-level shape.
export function parseDraft(raw: unknown): Graph | null {
  if (typeof raw !== "object" || raw === null) return null;
  const g = raw as Partial<Graph>;
  if (g.schema_version !== 1 || !Array.isArray(g.nodes) || !Array.isArray(g.edges)) return null;
  return { ...(g as Graph), variables: Array.isArray(g.variables) ? g.variables : [] };
}
