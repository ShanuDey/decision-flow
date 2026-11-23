import { NAME_MAX } from "@/lib/connections";

import { parseDraft } from "./convert";
import type { Graph } from "./types";

export const FILE_FORMAT = "decision-flow.flow";
export const FILE_VERSION = 1;
export const MAX_IMPORT_BYTES = 5 * 1024 * 1024;

const HINTS_MAX = 100;
const ID_MAX = 64;

// What a connection was, so the importer can offer a match. Never a secret or a host.
export interface ConnectionHint {
  type: string;
  name: string;
}

export interface ConnectionRef {
  id: string;
  name: string;
  typeId: string;
}

export interface FlowFile {
  format: typeof FILE_FORMAT;
  version: typeof FILE_VERSION;
  name: string;
  graph: Graph;
  connections?: Record<string, ConnectionHint>;
}

export type ImportResult =
  | {
      ok: true;
      name: string | null;
      graph: Graph;
      clearedSubflows: number;
      connections: Record<string, ConnectionHint>;
    }
  | { ok: false; message: string };

// Any node that calls out with a connection keeps its id in `data.connection_id`.
function connectionIdOf(node: Graph["nodes"][number]): string {
  const id = (node.data as { connection_id?: unknown }).connection_id;
  return typeof id === "string" ? id : "";
}

export function usedConnectionIds(graph: Graph): string[] {
  const ids = new Set<string>();
  for (const node of graph.nodes) {
    const id = connectionIdOf(node);
    if (id) ids.add(id);
  }
  return [...ids];
}

function hintsFor(graph: Graph, known: ConnectionRef[]): Record<string, ConnectionHint> {
  const byId = new Map(known.map((c) => [c.id, c]));
  const hints: Record<string, ConnectionHint> = {};
  for (const id of usedConnectionIds(graph)) {
    const found = byId.get(id);
    if (found) hints[id] = { type: found.typeId, name: found.name };
  }
  return hints;
}

export function buildFlowFile(name: string, graph: Graph, known: ConnectionRef[] = []): FlowFile {
  const connections = hintsFor(graph, known);
  const file: FlowFile = { format: FILE_FORMAT, version: FILE_VERSION, name, graph };
  return Object.keys(connections).length > 0 ? { ...file, connections } : file;
}

function readHints(raw: unknown): Record<string, ConnectionHint> {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) return {};
  const hints: Record<string, ConnectionHint> = {};
  for (const [id, value] of Object.entries(raw).slice(0, HINTS_MAX)) {
    if (id.length > ID_MAX || typeof value !== "object" || value === null) continue;
    const { type, name } = value as Record<string, unknown>;
    if (typeof type !== "string" || typeof name !== "string") continue;
    if (type.length > ID_MAX || name.length > NAME_MAX) continue;
    hints[id] = { type, name };
  }
  return hints;
}

export interface ConnectionNeed {
  fileId: string;
  name: string;
  type: string;
  nodes: number;
  // A connection here to offer first; applied only if the user confirms it.
  suggestion: string | null;
}

function suggest(hint: ConnectionHint | undefined, here: ConnectionRef[]): string | null {
  if (!hint) return null;
  const sameType = here.filter((c) => c.typeId === hint.type);
  return (sameType.find((c) => c.name === hint.name) ?? (sameType.length === 1 ? sameType[0] : null))?.id ?? null;
}

export function planConnections(
  graph: Graph,
  hints: Record<string, ConnectionHint>,
  here: ConnectionRef[],
): ConnectionNeed[] {
  const have = new Set(here.map((c) => c.id));
  const counts = new Map<string, number>();
  for (const node of graph.nodes) {
    const id = connectionIdOf(node);
    if (id) counts.set(id, (counts.get(id) ?? 0) + 1);
  }
  return [...counts]
    .filter(([id]) => !have.has(id))
    .map(([id, nodes]) => ({
      fileId: id,
      name: hints[id]?.name ?? "A connection",
      type: hints[id]?.type ?? "",
      nodes,
      suggestion: suggest(hints[id], here),
    }));
}

// A chosen connection replaces the file's id; any other id this workspace lacks is cleared.
export function applyConnections(graph: Graph, choices: Record<string, string>, here: ConnectionRef[]): Graph {
  const have = new Set(here.map((c) => c.id));
  const nodes = graph.nodes.map((node) => {
    const id = connectionIdOf(node);
    if (!id) return node;
    const next = id in choices ? choices[id] : have.has(id) ? id : "";
    return next === id ? node : ({ ...node, data: { ...node.data, connection_id: next } } as typeof node);
  });
  return { ...graph, nodes };
}

export function flowFileName(name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
  return `${slug || "flow"}.flow.json`;
}

// Subflow and agent tool ids belong to the exporting workspace, so an import must not keep them.
function clearSubflows(graph: Graph): { graph: Graph; cleared: number } {
  let cleared = 0;
  const nodes = graph.nodes.map((node) => {
    if (node.type === "agent") {
      const used = node.data.tools.filter((t) => t.flow_id).length;
      if (used === 0) return node;
      cleared += used;
      return { ...node, data: { ...node.data, tools: node.data.tools.map((t) => ({ ...t, flow_id: "" })) } };
    }
    if (node.type !== "subflow" || !node.data.flow_id) return node;
    cleared += 1;
    return { ...node, data: { ...node.data, flow_id: "" } };
  });
  return { graph: { ...graph, nodes }, cleared };
}

export function parseFlowFile(text: string): ImportResult {
  if (text.length > MAX_IMPORT_BYTES) return { ok: false, message: "The file is too large to import." };
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    return { ok: false, message: "The file is not valid JSON." };
  }
  if (typeof raw !== "object" || raw === null) return { ok: false, message: "The file is not a flow." };
  const body = raw as Record<string, unknown>;
  const wrapped = body.format === FILE_FORMAT;
  if (wrapped && body.version !== FILE_VERSION) {
    return { ok: false, message: "This file was made by a newer version and cannot be imported." };
  }
  const graph = parseDraft(wrapped ? body.graph : body);
  if (!graph) return { ok: false, message: "The file does not contain a valid flow graph." };
  const { graph: cleaned, cleared } = clearSubflows(graph);
  const name = wrapped && typeof body.name === "string" && body.name.trim() ? body.name.trim() : null;
  const connections = wrapped ? readHints(body.connections) : {};
  return { ok: true, name, graph: cleaned, clearedSubflows: cleared, connections };
}
