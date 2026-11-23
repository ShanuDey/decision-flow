import type { ConnectionOption } from "@/lib/connections";

// The node calls `<base_url>/chat/completions`, so the connection needs a base URL.
export const COMPATIBLE_TYPE = "openai_compatible";

export type NumberParse = { ok: true; value: number | null } | { ok: false; error: string };

export function parseTemperature(text: string): NumberParse {
  if (!text.trim()) return { ok: true, value: null };
  const value = Number(text);
  return Number.isFinite(value) && value >= 0 && value <= 2
    ? { ok: true, value }
    : { ok: false, error: "Enter a number from 0 to 2" };
}

export function parseMaxTokens(text: string): NumberParse {
  if (!text.trim()) return { ok: true, value: null };
  const value = Number(text);
  return Number.isInteger(value) && value >= 1
    ? { ok: true, value }
    : { ok: false, error: "Enter a whole number, at least 1" };
}

// Keeps the chosen connection listed so it never silently disappears.
export function promptConnections(all: ConnectionOption[], current: string): ConnectionOption[] {
  return all.filter((c) => c.typeId === COMPATIBLE_TYPE || c.id === current);
}

export function lacksBaseUrl(chosen: ConnectionOption | undefined): boolean {
  return chosen !== undefined && chosen.typeId !== COMPATIBLE_TYPE;
}
