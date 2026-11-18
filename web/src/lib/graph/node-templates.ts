import type { NodeTemplate } from "@/lib/api/models";
import type { CatalogItem } from "@/lib/catalog";
import { type ConnectionOption, hostAllowed } from "@/lib/connections";

import { defaultData } from "./nodes";
import type { HttpRequestData } from "./types";

export const BUILT_IN = "Built-in";

export function templateItems(templates: NodeTemplate[]): CatalogItem[] {
  return templates.map((t) => ({
    id: t.id,
    name: t.name,
    description: t.description,
    icon: t.icon ?? "plug",
    docsUrl: t.docs_url ?? "",
    group: BUILT_IN,
    tags: t.tags ?? [],
  }));
}

export type ConnectionNeed =
  | { kind: "none" }
  | { kind: "picked"; connection: ConnectionOption }
  | { kind: "choose"; typeName: string }
  | { kind: "missing"; typeId: string }
  | { kind: "blocked"; typeName: string; host: string };

// The host written in the template's URL, or null when part of it is a placeholder.
function urlHost(url: string): string | null {
  const match = /^https?:\/\/([^/?#:]+)/i.exec(url.trim());
  return match && !match[1].includes("{{") ? match[1].toLowerCase() : null;
}

function candidates(template: NodeTemplate, connections: ConnectionOption[]) {
  const ofType = connections.filter((c) => c.typeId === template.connection?.type);
  const host = urlHost(template.data.url ?? "");
  const usable = host ? ofType.filter((c) => hostAllowed(host, c.hosts)) : ofType;
  return { ofType, usable, host };
}

// A connection only counts when it is the right type and allows the host the template calls.
export function connectionNeed(template: NodeTemplate, connections: ConnectionOption[]): ConnectionNeed {
  if (!template.connection) return { kind: "none" };
  const { ofType, usable, host } = candidates(template, connections);
  if (ofType.length === 0) return { kind: "missing", typeId: template.connection.type };
  if (usable.length === 0) return { kind: "blocked", typeName: ofType[0].typeName, host: host ?? "" };
  if (usable.length === 1) return { kind: "picked", connection: usable[0] };
  return { kind: "choose", typeName: usable[0].typeName };
}

function sameValue(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== "object" || typeof b !== "object" || a === null || b === null) return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  const left = a as Record<string, unknown>;
  const right = b as Record<string, unknown>;
  const keys = Object.keys(left);
  return keys.length === Object.keys(right).length && keys.every((k) => k in right && sameValue(left[k], right[k]));
}

// Ignores the connection and key order: the server returns saved settings in its own order.
export function isBlank(config: HttpRequestData): boolean {
  return sameValue({ ...config, connection_id: "" }, defaultData("http_request"));
}

// Keeps the node's connection only if it still fits; a lone fitting connection is picked.
export function applyTemplate(
  template: NodeTemplate,
  connections: ConnectionOption[],
  current: HttpRequestData,
): HttpRequestData {
  const { usable } = candidates(template, connections);
  const need = connectionNeed(template, connections);
  const keep = usable.some((c) => c.id === current.connection_id) ? current.connection_id : "";
  return {
    ...defaultData("http_request"),
    ...structuredClone(template.data),
    connection_id: need.kind === "picked" ? need.connection.id : keep,
  } as HttpRequestData;
}
