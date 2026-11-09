import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type EdgeChange,
  type NodeChange,
} from "@xyflow/react";
import { create } from "zustand";

import type { FieldIssue } from "@/lib/call";
import {
  type EditorGraph,
  type FlowEdge,
  type FlowNode,
  fromReactFlow,
  toReactFlow,
} from "@/lib/graph/convert";
import { canAdd, canConnect, createNode, NODE_SPECS } from "@/lib/graph/nodes";
import type { Graph, NodeData, NodeType, Variable } from "@/lib/graph/types";

interface EditorState {
  flowId: string;
  name: string;
  draftVersion: number;
  nodes: FlowNode[];
  edges: FlowEdge[];
  variables: Variable[];
  dirty: boolean;
  // bumped on every graph change, so a save can tell whether edits landed while it was in flight
  revision: number;
  savedAt: Date | null;
  issues: FieldIssue[];

  load: (flow: { id: string; name: string; draftVersion: number; graph: Graph }) => void;
  toGraph: () => Graph;
  onNodesChange: (changes: NodeChange<FlowNode>[]) => void;
  onEdgesChange: (changes: EdgeChange<FlowEdge>[]) => void;
  onConnect: (connection: Connection) => void;
  isValidConnection: (connection: Connection | FlowEdge) => boolean;
  addNode: (type: NodeType) => void;
  setNodeConfig: (id: string, config: NodeData) => void;
  renameNode: (id: string, name: string) => void;
  setVariables: (variables: Variable[]) => void;
  setIssues: (issues: FieldIssue[]) => void;
  markSaved: (draftVersion: number, savedRevision: number) => void;
}

// A change only makes the draft dirty if it alters the graph, not the selection or measuring.
function altersGraph(change: NodeChange | EdgeChange): boolean {
  if (change.type === "select" || change.type === "dimensions") return false;
  if (change.type === "position") return change.dragging === false;
  return true;
}

// Marks the draft changed (or leaves it as is when `changed` is false).
const touch = (s: { dirty: boolean; revision: number }, changed = true) =>
  changed ? { dirty: true, revision: s.revision + 1 } : { dirty: s.dirty, revision: s.revision };

const typeOf = (nodes: FlowNode[], id: string | null | undefined) =>
  nodes.find((n) => n.id === id)?.type;

export const useEditor = create<EditorState>()((set, get) => ({
  flowId: "",
  name: "",
  draftVersion: 1,
  nodes: [],
  edges: [],
  variables: [],
  dirty: false,
  revision: 0,
  savedAt: null,
  issues: [],

  load: ({ id, name, draftVersion, graph }) =>
    set({
      flowId: id,
      name,
      draftVersion,
      ...toReactFlow(graph),
      dirty: false,
      revision: 0,
      savedAt: null,
      issues: [],
    }),

  toGraph: () => {
    const { nodes, edges, variables }: EditorGraph = get();
    return fromReactFlow({ nodes, edges, variables });
  },

  onNodesChange: (changes) =>
    set((s) => {
      // Never delete the last node of a type that the flow needs (Start, End).
      const remaining = { ...countByType(s.nodes) };
      const allowed = changes.filter((c) => {
        if (c.type !== "remove") return true;
        const type = typeOf(s.nodes, c.id);
        if (!type) return true;
        if (remaining[type] <= NODE_SPECS[type].minCount) return false;
        remaining[type] -= 1;
        return true;
      });
      const gone = new Set(allowed.filter((c) => c.type === "remove").map((c) => c.id));
      return {
        nodes: applyNodeChanges(allowed, s.nodes),
        edges: gone.size
          ? s.edges.filter((e) => !gone.has(e.source) && !gone.has(e.target))
          : s.edges,
        ...touch(s, allowed.some(altersGraph)),
      };
    }),

  onEdgesChange: (changes) =>
    set((s) => ({
      edges: applyEdgeChanges(changes, s.edges),
      ...touch(s, changes.some(altersGraph)),
    })),

  isValidConnection: (c) => {
    const { nodes, edges } = get();
    const source = typeOf(nodes, c.source);
    const target = typeOf(nodes, c.target);
    if (!source || !target || c.source === c.target) return false;
    if (!canConnect(source, target)) return false;
    return !edges.some((e) => e.source === c.source && e.target === c.target);
  },

  onConnect: (connection) =>
    set((s) => ({ edges: addEdge(connection, s.edges), ...touch(s) })),

  addNode: (type) =>
    set((s) => {
      if (!canAdd(type, s.nodes.map(refOf))) return s;
      const x = s.nodes.length ? Math.max(...s.nodes.map((n) => n.position.x)) + 280 : 0;
      const y = s.nodes.length ? s.nodes[s.nodes.length - 1].position.y : 0;
      const node = createNode(type, s.nodes.map(refOf), { x, y });
      const added: FlowNode = {
        id: node.id,
        type: node.type,
        position: node.position,
        data: { name: node.name, config: node.data },
        selected: true,
      };
      return {
        nodes: [...s.nodes.map((n) => ({ ...n, selected: false })), added],
        ...touch(s),
      };
    }),

  setNodeConfig: (id, config) =>
    set((s) => ({
      nodes: s.nodes.map((n) => (n.id === id ? { ...n, data: { ...n.data, config } } : n)),
      ...touch(s),
    })),

  renameNode: (id, name) =>
    set((s) => ({
      nodes: s.nodes.map((n) => (n.id === id ? { ...n, data: { ...n.data, name } } : n)),
      ...touch(s),
    })),

  setVariables: (variables) => set((s) => ({ variables, ...touch(s) })),

  setIssues: (issues) => set({ issues }),

  markSaved: (draftVersion, savedRevision) =>
    set((s) => ({ draftVersion, dirty: s.revision !== savedRevision, savedAt: new Date() })),
}));

const refOf = (n: FlowNode) => ({ id: n.id, name: n.data.name, type: n.type as NodeType });

function countByType(nodes: FlowNode[]): Record<NodeType, number> {
  const counts: Record<NodeType, number> = { start: 0, assign: 0, end: 0 };
  for (const n of nodes) counts[n.type as NodeType] += 1;
  return counts;
}

export const selectedNode = (s: EditorState): FlowNode | undefined =>
  s.nodes.find((n) => n.selected);
