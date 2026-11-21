import type { IndexEntry, InstalledSummary } from "@/lib/api/models";

export type Kind = IndexEntry["kind"];
export type Status = "available" | "installed" | "update";

export interface MarketEntry extends IndexEntry {
  status: Status;
  installedVersion: string | null;
  // Names of the entries this one needs that are not installed yet.
  alsoInstalls: string[];
}

export const KIND_LABELS: Record<Kind, string> = {
  "connection-type": "Connection",
  "node-template": "Template",
};

const keyOf = (kind: string, id: string) => `${kind}/${id}`;

export function joinCatalog(entries: IndexEntry[], installed: InstalledSummary[]): MarketEntry[] {
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

export function filterEntries(entries: MarketEntry[], { query, kinds }: Filter): MarketEntry[] {
  const needle = query.trim().toLowerCase();
  return entries.filter(
    (e) =>
      (!kinds || kinds.includes(e.kind)) &&
      (!needle || `${e.name} ${e.description} ${e.tags.join(" ")}`.toLowerCase().includes(needle)),
  );
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
