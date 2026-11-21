import MiniSearch from "minisearch";

import type { InstalledSummary, ListedEntry } from "@/lib/api/models";

export type Kind = ListedEntry["kind"];
export type Status = "available" | "installed" | "update";

export interface MarketEntry extends ListedEntry {
  status: Status;
  installedVersion: string | null;
  // Names of the entries this one needs that are not installed yet.
  alsoInstalls: string[];
}

export const KIND_LABELS: Record<Kind, string> = {
  "connection-type": "Connection",
  "node-template": "Template",
  flow: "Flow",
};

const keyOf = (kind: string, id: string) => `${kind}/${id}`;

export const isBroken = (entry: ListedEntry) => entry.health === "broken";

// Installing or updating is paused for a broken item; removing and what is installed are not.
export const canInstall = (entry: MarketEntry) => entry.status !== "installed" && !isBroken(entry);

export function healthNote(entry: MarketEntry): string | null {
  if (!isBroken(entry)) return null;
  const why = entry.health_reason ? ` (${entry.health_reason})` : "";
  return entry.status === "installed"
    ? `Reported broken upstream${why}. Your installed copy keeps working.`
    : `Reported broken${why}. Installing is paused until a later check passes.`;
}

export function joinCatalog(entries: ListedEntry[], installed: InstalledSummary[]): MarketEntry[] {
  const have = new Map(installed.map((i) => [keyOf(i.kind, i.id), i]));
  const names = new Map(entries.map((e) => [keyOf(e.kind, e.id), e.name]));
  return entries.map((entry) => {
    const found = have.get(keyOf(entry.kind, entry.id));
    const status: Status = !found ? "available" : found.hash === entry.hash ? "installed" : "update";
    const alsoInstalls = entry.requires
      .filter((need) => !have.has(need))
      .map((need) => names.get(need) ?? need);
    return { ...entry, status, installedVersion: found?.version ?? null, alsoInstalls };
  });
}

export interface Filter {
  query: string;
  kinds: Kind[] | null;
}

const searchIndexes = new WeakMap<MarketEntry[], MiniSearch>();

// One index per entries array: typing re-queries it, and only a new list rebuilds it.
function searchIndex(entries: MarketEntry[]): MiniSearch {
  let index = searchIndexes.get(entries);
  if (!index) {
    index = new MiniSearch({ idField: "key", fields: ["name", "description", "tags"] });
    index.addAll(
      entries.map((e) => ({ key: keyOf(e.kind, e.id), name: e.name, description: e.description, tags: e.tags.join(" ") })),
    );
    searchIndexes.set(entries, index);
  }
  return index;
}

const SEARCH_OPTIONS = { prefix: true, fuzzy: 0.2, combineWith: "AND", boost: { name: 3, tags: 2 } } as const;

export function filterEntries(entries: MarketEntry[], { query, kinds }: Filter): MarketEntry[] {
  const inKinds = (e: MarketEntry) => !kinds || kinds.includes(e.kind);
  if (!query.trim()) return entries.filter(inKinds);
  const byKey = new Map(entries.map((e) => [keyOf(e.kind, e.id), e]));
  return searchIndex(entries)
    .search(query, SEARCH_OPTIONS)
    .flatMap((hit) => byKey.get(hit.id) ?? [])
    .filter(inKinds);
}

export function installBody(entry: MarketEntry) {
  return { kind: entry.kind, id: entry.id, version: entry.version, hash: entry.hash };
}

export function relativeTime(iso: string, now: number): string {
  const seconds = Math.max(0, Math.round((now - Date.parse(iso)) / 1000));
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}
