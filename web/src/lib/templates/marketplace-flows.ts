import type { InstalledFlow, Template } from "@/lib/api/models";
import { parseDraft } from "@/lib/graph/convert";
import type { ImportResult } from "@/lib/graph/transfer";

export const MARKETPLACE_CATEGORY = "Marketplace";
const PREFIX = "marketplace:";

// An installed flow is offered in the picker like a built-in template, under its own category.
export function flowAsTemplate(flow: InstalledFlow): Template {
  const nodes = Array.isArray(flow.draft.nodes) ? (flow.draft.nodes as { type: string }[]) : [];
  return {
    id: `${PREFIX}${flow.id}`,
    title: flow.name,
    summary: flow.description,
    description: flow.description,
    category: MARKETPLACE_CATEGORY,
    inputs: flow.inputs,
    outputs: flow.outputs,
    node_types: [...new Set(nodes.map((n) => n.type))].sort(),
    draft: flow.draft,
  };
}

export const isMarketplaceTemplate = (id: string) => id.startsWith(PREFIX);

// The same shape an imported file has, so its connection slots go through the matching window.
export function flowAsImport(flow: InstalledFlow, name: string): Extract<ImportResult, { ok: true }> | null {
  const graph = parseDraft(flow.draft);
  return graph ? { ok: true, name, graph, clearedSubflows: 0, connections: flow.connections } : null;
}

export const findInstalledFlow = (flows: InstalledFlow[], templateId: string) =>
  flows.find((f) => `${PREFIX}${f.id}` === templateId);
