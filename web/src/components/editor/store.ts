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
import {
  canAdd,
  canConnect,
  createNode,
  NODE_SPECS,
  uniqueId,
  uniqueName,
} from "@/lib/graph/nodes";
import {
  type Contracts,
  type FlowContract,
  type PublishedFlow,
} from "@/lib/graph/subflow";
import type {
  AssignData,
  Graph,
  NodeData,
  NodeType,
  Position,
  Variable,
} from "@/lib/graph/types";

import type { PublishedInfo } from "./published";

export interface Removed {
  nodes: FlowNode[];
  edges: FlowEdge[];
}

interface EditorState {
  flowId: string;
  name: string;
  draftVersion: number;
  // Latest published version and the draft version it was published from.
  publishedVersion: number | null;
  publishedDraftVersion: number | null;
  nodes: FlowNode[];
  edges: FlowEdge[];
  variables: Variable[];
  dirty: boolean;
  // bumped on every graph change, so a save can tell whether edits landed while it was in flight
  revision: number;
  savedAt: Date | null;
  issues: FieldIssue[];
  // Names of the workspace's saved secrets, for fields that accept them. Never the values.
  secretNames: string[];
  // Flows a Subflow node can call, and what each declares; loaded on demand, never saved.
  publishedFlows: PublishedFlow[];
  contracts: Contracts;
  // UI only: the top bar button and the Assign dropdown both open the variables dialog.
  variablesOpen: boolean;
  variablesSelected: number;
  setVariablesOpen: (open: boolean) => void;
  openVariables: (selected?: number) => void;
  selectVariable: (index: number) => void;

  load: (flow: {
    id: string;
    name: string;
    draftVersion: number;
    graph: Graph;
    published?: PublishedInfo | null;
  }) => void;
  // Saved by its own endpoint, so it never dirties the draft.
  setName: (name: string) => void;
  toGraph: () => Graph;
  onNodesChange: (changes: NodeChange<FlowNode>[]) => void;
  onEdgesChange: (changes: EdgeChange<FlowEdge>[]) => void;
  onConnect: (connection: Connection) => void;
  isValidConnection: (connection: Connection | FlowEdge) => boolean;
  // `from` also connects the new node to that node's output (the contextual "+" on a handle).
  addNode: (type: NodeType, position?: Position, from?: { id: string; handle: string | null }) => void;
  // Selection is not a graph change: it never makes the draft dirty.
  selectOnly: (id: string) => void;
  // Returns the new node's id, or null when it cannot be duplicated (at the type's limit).
  duplicateNode: (id: string) => string | null;
  // Returns exactly what was removed (a removed node takes its edges with it), for Undo.
  deleteItems: (nodeIds: string[], edgeIds: string[]) => Removed;
  restore: (removed: Removed) => void;
  setNodeConfig: (id: string, config: NodeData) => void;
  renameNode: (id: string, name: string) => void;
  setVariables: (variables: Variable[]) => void;
  // Also repoints Assign targets that used the old name; skipped when it would merge two variables.
  renameVariable: (index: number, name: string) => void;
  setIssues: (issues: FieldIssue[]) => void;
  setSecretNames: (names: string[]) => void;
  setPublishedFlows: (flows: PublishedFlow[]) => void;
  setContract: (flowId: string, contract: FlowContract | null) => void;
  markSaved: (draftVersion: number, savedRevision: number) => void;
  markPublished: (version: number, draftVersion: number) => void;
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

const refOf = (n: FlowNode) => ({ id: n.id, name: n.data.name, type: n.type as NodeType });

function countByType(nodes: FlowNode[]): Record<NodeType, number> {
  const counts: Record<NodeType, number> = {
    start: 0,
    assign: 0,
    condition: 0,
    http_request: 0,
    subflow: 0,
    end: 0,
  };
  for (const n of nodes) counts[n.type as NodeType] += 1;
  return counts;
}

// Never delete the last node of a type that the flow needs (Start, End).
export function removableIds(nodes: FlowNode[], ids: string[]): Set<string> {
  const remaining = countByType(nodes);
  const allowed = new Set<string>();
  for (const id of ids) {
    const type = typeOf(nodes, id) as NodeType | undefined;
    if (!type || remaining[type] <= NODE_SPECS[type].minCount) continue;
    remaining[type] -= 1;
    allowed.add(id);
  }
  return allowed;
}

export const useEditor = create<EditorState>()((set, get) => ({
  flowId: "",
  name: "",
  draftVersion: 1,
  publishedVersion: null,
  publishedDraftVersion: null,
  nodes: [],
  edges: [],
  variables: [],
  dirty: false,
  revision: 0,
  savedAt: null,
  issues: [],
  secretNames: [],
  publishedFlows: [],
  contracts: {},
  variablesOpen: false,
  variablesSelected: 0,
  setVariablesOpen: (variablesOpen) => set({ variablesOpen }),
  openVariables: (selected = 0) => set({ variablesOpen: true, variablesSelected: selected }),
  selectVariable: (variablesSelected) => set({ variablesSelected }),

  load: ({ id, name, draftVersion, graph, published }) =>
    set({
      flowId: id,
      name,
      draftVersion,
      publishedVersion: published?.version ?? null,
      publishedDraftVersion: published?.draftVersion ?? null,
      ...toReactFlow(graph),
      dirty: false,
      revision: 0,
      savedAt: null,
      issues: [],
    }),

  setName: (name) => set({ name }),

  toGraph: () => {
    const { nodes, edges, variables }: EditorGraph = get();
    return fromReactFlow({ nodes, edges, variables });
  },

  onNodesChange: (changes) =>
    set((s) => {
      // Safety net: deletes normally go through deleteItems.
      const allowedIds = removableIds(
        s.nodes,
        changes.filter((c) => c.type === "remove").map((c) => c.id),
      );
      const allowed = changes.filter((c) => c.type !== "remove" || allowedIds.has(c.id));
      return {
        nodes: applyNodeChanges(allowed, s.nodes),
        edges: allowedIds.size
          ? s.edges.filter((e) => !allowedIds.has(e.source) && !allowedIds.has(e.target))
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
    if (NODE_SPECS[source].handles.length > 0) {
      // a branch node takes one edge per handle
      return (
        !!c.sourceHandle &&
        !edges.some((e) => e.source === c.source && e.sourceHandle === c.sourceHandle)
      );
    }
    return !edges.some((e) => e.source === c.source && e.target === c.target);
  },

  onConnect: (connection) => set((s) => ({ edges: addEdge(connection, s.edges), ...touch(s) })),

  addNode: (type, position, from) =>
    set((s) => {
      if (!canAdd(type, s.nodes.map(refOf))) return s;
      const source = from ? s.nodes.find((n) => n.id === from.id) : undefined;
      if (from && (!source || !canConnect(source.type as NodeType, type))) return s;
      const x = s.nodes.length ? Math.max(...s.nodes.map((n) => n.position.x)) + 280 : 0;
      const y = s.nodes.length ? s.nodes[s.nodes.length - 1].position.y : 0;
      const spot = position ?? (source ? { x: source.position.x + 280, y: source.position.y } : { x, y });
      const node = createNode(type, s.nodes.map(refOf), spot);
      const added: FlowNode = {
        id: node.id,
        type: node.type,
        position: node.position,
        data: { name: node.name, config: node.data },
        selected: true,
      };
      const wire = from && source;
      return {
        nodes: [...s.nodes.map((n) => ({ ...n, selected: false })), added],
        edges: wire
          ? addEdge(
              { source: from.id, sourceHandle: from.handle, target: added.id, targetHandle: null },
              s.edges,
            )
          : s.edges,
        ...touch(s),
      };
    }),

  selectOnly: (id) =>
    set((s) => ({ nodes: s.nodes.map((n) => ({ ...n, selected: n.id === id })) })),

  duplicateNode: (id) => {
    const { nodes } = get();
    const source = nodes.find((n) => n.id === id);
    if (!source || !canAdd(source.type as NodeType, nodes.map(refOf))) return null;
    const name = uniqueName(
      source.data.name,
      nodes.map((n) => n.data.name),
    );
    const newId = uniqueId(
      name,
      source.type as NodeType,
      nodes.map((n) => n.id),
    );
    const copy: FlowNode = {
      id: newId,
      type: source.type,
      position: { x: source.position.x + 40, y: source.position.y + 40 },
      data: { name, config: structuredClone(source.data.config) },
      selected: true,
    };
    set((s) => ({
      nodes: [...s.nodes.map((n) => ({ ...n, selected: false })), copy],
      ...touch(s),
    }));
    return newId;
  },

  deleteItems: (nodeIds, edgeIds) => {
    const s = get();
    const gone = removableIds(s.nodes, nodeIds);
    const dropped = new Set(edgeIds);
    const removed: Removed = {
      nodes: s.nodes.filter((n) => gone.has(n.id)),
      edges: s.edges.filter((e) => dropped.has(e.id) || gone.has(e.source) || gone.has(e.target)),
    };
    if (!removed.nodes.length && !removed.edges.length) return removed;
    const removedEdgeIds = new Set(removed.edges.map((e) => e.id));
    set((st) => ({
      nodes: st.nodes.filter((n) => !gone.has(n.id)),
      edges: st.edges.filter((e) => !removedEdgeIds.has(e.id)),
      ...touch(st),
    }));
    return removed;
  },

  restore: ({ nodes, edges }) =>
    set((s) => {
      const have = new Set(s.nodes.map((n) => n.id));
      const addedNodes = nodes
        .filter((n) => !have.has(n.id))
        .map((n) => ({ ...n, selected: false }));
      // A removed node whose id is now taken stays gone; its edges must not attach to the new one.
      const blocked = new Set(nodes.filter((n) => have.has(n.id)).map((n) => n.id));
      const ends = new Set([...have, ...addedNodes.map((n) => n.id)]);
      const haveEdges = new Set(s.edges.map((e) => e.id));
      const addedEdges = edges.filter(
        (e) =>
          !haveEdges.has(e.id) &&
          ends.has(e.source) &&
          ends.has(e.target) &&
          !blocked.has(e.source) &&
          !blocked.has(e.target),
      );
      if (!addedNodes.length && !addedEdges.length) return s;
      return {
        nodes: [...s.nodes, ...addedNodes],
        edges: [...s.edges, ...addedEdges],
        ...touch(s),
      };
    }),

  setNodeConfig: (id, config) =>
    set((s) => ({
      nodes: s.nodes.map((n) => (n.id === id ? { ...n, data: { ...n.data, config } } : n)),
      ...touch(s),
    })),

  renameVariable: (index, name) =>
    set((s) => {
      const old = s.variables[index]?.name;
      if (old === undefined) return {};
      const variables = s.variables.map((v, i) => (i === index ? { ...v, name } : v));
      const safe =
        old !== "" && s.variables.every((v, i) => i === index || (v.name !== old && v.name !== name));
      const repoint = (n: FlowNode): FlowNode => {
        if (n.type !== "assign") return n;
        const config = n.data.config as AssignData;
        const assignments = config.assignments.map((a) =>
          a.variable === old ? { ...a, variable: name } : a,
        );
        return { ...n, data: { ...n.data, config: { ...config, assignments } } };
      };
      return { variables, nodes: safe ? s.nodes.map(repoint) : s.nodes, ...touch(s) };
    }),

  renameNode: (id, name) =>
    set((s) => ({
      nodes: s.nodes.map((n) => (n.id === id ? { ...n, data: { ...n.data, name } } : n)),
      ...touch(s),
    })),

  setVariables: (variables) => set((s) => ({ variables, ...touch(s) })),

  setIssues: (issues) => set({ issues }),
  setSecretNames: (secretNames) => set({ secretNames }),
  setPublishedFlows: (publishedFlows) => set({ publishedFlows }),
  setContract: (flowId, contract) => set((s) => ({ contracts: { ...s.contracts, [flowId]: contract } })),

  markSaved: (draftVersion, savedRevision) =>
    set((s) => ({ draftVersion, dirty: s.revision !== savedRevision, savedAt: new Date() })),

  markPublished: (publishedVersion, publishedDraftVersion) =>
    set({ publishedVersion, publishedDraftVersion }),
}));

export const selectedNode = (s: EditorState): FlowNode | undefined =>
  s.nodes.find((n) => n.selected);
