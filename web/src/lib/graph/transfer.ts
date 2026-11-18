import { parseDraft } from "./convert";
import type { Graph } from "./types";

export const FILE_FORMAT = "decision-flow.flow";
export const FILE_VERSION = 1;
export const MAX_IMPORT_BYTES = 5 * 1024 * 1024;

export interface FlowFile {
  format: typeof FILE_FORMAT;
  version: typeof FILE_VERSION;
  name: string;
  graph: Graph;
}

export type ImportResult =
  | { ok: true; name: string | null; graph: Graph; clearedSubflows: number }
  | { ok: false; message: string };

export function buildFlowFile(name: string, graph: Graph): FlowFile {
  return { format: FILE_FORMAT, version: FILE_VERSION, name, graph };
}

export function flowFileName(name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
  return `${slug || "flow"}.flow.json`;
}

// Subflow ids belong to the exporting workspace, so an import must not keep them.
function clearSubflows(graph: Graph): { graph: Graph; cleared: number } {
  let cleared = 0;
  const nodes = graph.nodes.map((node) => {
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
  return { ok: true, name, graph: cleaned, clearedSubflows: cleared };
}
