import type { HttpRequestData } from "./types";

export type Method = HttpRequestData["method"];
export type BodyType = HttpRequestData["body_type"];

export const METHODS: Method[] = ["GET", "POST", "PUT", "PATCH", "DELETE"];

export const BODY_TYPES: { value: BodyType; label: string }[] = [
  { value: "none", label: "No body" },
  { value: "json", label: "JSON" },
  { value: "form", label: "Form (URL-encoded)" },
  { value: "text", label: "Text" },
];

const HEADER_NAME = /^[A-Za-z0-9!#$%&'*+.^_`|~-]+$/;

export interface Row {
  name: string;
  value: string;
}

export type NameCheck = (name: string) => string | null;

// The server sets these itself; they mirror FRAMING_HEADERS in the API.
const RESERVED_HEADERS = new Set([
  "host",
  "content-length",
  "transfer-encoding",
  "connection",
  "keep-alive",
  "proxy-connection",
  "te",
  "trailer",
  "upgrade",
]);

export const headerNameCheck: NameCheck = (name) => {
  if (!HEADER_NAME.test(name)) return "Not a valid header name";
  return RESERVED_HEADERS.has(name.toLowerCase()) ? "This header is set by the server" : null;
};

export const rowsOf = (record: Record<string, string> | null | undefined): Row[] =>
  Object.entries(record ?? {}).map(([name, value]) => ({ name, value }));

// Why a row cannot be saved, or null; for a repeated name the later row is the one flagged.
export function rowProblem(
  rows: Row[],
  index: number,
  check?: NameCheck,
  caseInsensitive = false,
): string | null {
  const name = rows[index].name;
  if (!name.trim()) return "Enter a name";
  const invalid = check?.(name);
  if (invalid) return invalid;
  const same = (other: string) =>
    caseInsensitive ? other.toLowerCase() === name.toLowerCase() : other === name;
  return rows.findIndex((row) => same(row.name)) === index ? null : "This name is already used";
}

// Only rows without a problem reach the node; the rest stay in the form until fixed.
export function recordOf(
  rows: Row[],
  check?: NameCheck,
  caseInsensitive = false,
): Record<string, string> {
  const record: Record<string, string> = {};
  rows.forEach((row, i) => {
    if (!rowProblem(rows, i, check, caseInsensitive)) record[row.name] = row.value;
  });
  return record;
}

export function bodyOnTypeChange(from: BodyType, to: BodyType, body: unknown): unknown {
  if (from === to) return body;
  if (to === "none") return null;
  return to === "text" ? "" : {};
}

export const jsonText = (value: unknown): string => JSON.stringify(value ?? {}, null, 2);

export type JsonParse = { ok: true; value: unknown } | { ok: false; error: string };

export function parseJson(text: string): JsonParse {
  try {
    return { ok: true, value: JSON.parse(text) };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "Not valid JSON" };
  }
}

export type TimeoutParse = { ok: true; value: number | null } | { ok: false; error: string };

export function parseTimeout(text: string): TimeoutParse {
  if (!text.trim()) return { ok: true, value: null };
  const value = Number(text);
  return Number.isInteger(value) && value >= 1
    ? { ok: true, value }
    : { ok: false, error: "Enter a whole number of seconds, at least 1" };
}
