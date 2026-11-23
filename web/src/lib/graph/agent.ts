import type { NumberParse } from "./prompt";

export const MAX_ITERATIONS = 50;
export const DEFAULT_ITERATIONS = 8;

// Empty is not allowed: the agent always needs a step limit.
export function parseIterations(text: string): NumberParse {
  const value = Number(text);
  return text.trim() !== "" && Number.isInteger(value) && value >= 1 && value <= MAX_ITERATIONS
    ? { ok: true, value }
    : { ok: false, error: `Enter a whole number from 1 to ${MAX_ITERATIONS}` };
}

export function parseMaxSeconds(text: string): NumberParse {
  if (!text.trim()) return { ok: true, value: null };
  const value = Number(text);
  return Number.isInteger(value) && value >= 1
    ? { ok: true, value }
    : { ok: false, error: "Enter a whole number of seconds, at least 1" };
}

const NAME = /^[A-Za-z0-9_-]{1,64}$/;

// The name the model calls the tool by.
export function toolNameProblem(names: string[], index: number): string | null {
  const name = names[index];
  if (!name.trim()) return "Give the tool a name";
  if (!NAME.test(name)) return "Use 1 to 64 letters, digits, _ or -";
  return names.findIndex((n) => n === name) !== index ? "Another tool has this name" : null;
}
