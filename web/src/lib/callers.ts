export interface Caller {
  id: string;
  name: string;
}

const SHOWN = 3;

// The 409 `flow_in_use` answer lists the callers in `details.callers`.
export function callersOf(details: Record<string, unknown>): Caller[] {
  const raw = details.callers;
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((c) =>
    c && typeof c.id === "string" && typeof c.name === "string" ? [{ id: c.id, name: c.name }] : [],
  );
}

export function calledByText(callers: Caller[]): string {
  const names = callers.slice(0, SHOWN).map((c) => c.name);
  const more = callers.length - names.length;
  const noun = callers.length === 1 ? "flow" : "flows";
  return `Called by ${callers.length} ${noun}: ${names.join(", ")}${more > 0 ? ` and ${more} more` : ""}`;
}
