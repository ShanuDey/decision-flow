export const PAGE_SIZE = 25;

const STATUSES = ["succeeded", "failed"] as const;
const TYPES = ["test", "live"] as const;

export type RunStatus = (typeof STATUSES)[number];
export type RunType = (typeof TYPES)[number];

export interface RunFilters {
  flow?: string;
  status?: RunStatus;
  type?: RunType;
}

export interface RunsQuery extends RunFilters {
  cursor?: string;
  back: string[];
}

type Raw = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string | undefined {
  return (Array.isArray(value) ? value[0] : value) || undefined;
}

function oneOf<T extends string>(allowed: readonly T[], value: string | undefined): T | undefined {
  return allowed.find((a) => a === value);
}

export function parseRunsQuery(raw: Raw): RunsQuery {
  return {
    flow: first(raw.flow),
    status: oneOf(STATUSES, first(raw.status)),
    type: oneOf(TYPES, first(raw.type)),
    cursor: first(raw.cursor),
    back: first(raw.back)?.split(",").filter(Boolean) ?? [],
  };
}

export function testParam(type: RunType | undefined): boolean | undefined {
  return type === undefined ? undefined : type === "test";
}

export function runsHref(filters: RunFilters, cursor?: string, back: string[] = []): string {
  const params = new URLSearchParams();
  if (filters.flow) params.set("flow", filters.flow);
  if (filters.status) params.set("status", filters.status);
  if (filters.type) params.set("type", filters.type);
  if (cursor) params.set("cursor", cursor);
  if (back.length > 0) params.set("back", back.join(","));
  const qs = params.toString();
  return qs ? `/runs?${qs}` : "/runs";
}

export function olderHref(query: RunsQuery, nextCursor: string): string {
  const back = query.cursor ? [...query.back, query.cursor] : query.back;
  return runsHref(query, nextCursor, back);
}

export function newerHref(query: RunsQuery): string | null {
  if (!query.cursor) return null;
  return runsHref(query, query.back.at(-1), query.back.slice(0, -1));
}
