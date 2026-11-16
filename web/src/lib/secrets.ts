export const NAME_MAX = 64;
export const VALUE_MIN = 8;
export const VALUE_MAX = 4096;

const NAME_PATTERN = /^[A-Z][A-Z0-9_]*$/;

export function normalizeName(raw: string): string {
  return raw
    .toUpperCase()
    .replace(/[\s-]+/g, "_")
    .replace(/[^A-Z0-9_]/g, "")
    .slice(0, NAME_MAX);
}

export function nameProblem(name: string): string | null {
  if (!name) return "Enter a name";
  if (!NAME_PATTERN.test(name)) return "Start with a letter";
  return null;
}

export function valueProblem(value: string): string | null {
  if (value.length < VALUE_MIN) return `The value must be at least ${VALUE_MIN} characters`;
  if (value.length > VALUE_MAX) return `The value can be at most ${VALUE_MAX} characters`;
  return null;
}
