import type { FieldType } from "./types";

// `object` is left out: a strict schema has to say what is inside it.
export const STRUCTURED_TYPES: { value: FieldType; label: string }[] = [
  { value: "string", label: "text" },
  { value: "number", label: "number" },
  { value: "boolean", label: "true / false" },
  { value: "enum", label: "one of a list" },
  { value: "array", label: "list of text" },
];

export const MODES = [
  { value: "schema", label: "Provider enforces the structure" },
  { value: "json", label: "Ask for a JSON object" },
] as const;

const NAME = /^[A-Za-z_][A-Za-z0-9_]*$/;

// The name a later node reads as `nodes.<id>.output.<name>`.
export function fieldNameProblem(names: string[], index: number): string | null {
  const name = names[index];
  if (!name.trim()) return "Give the field a name";
  if (!NAME.test(name)) return "Use letters, digits and underscores, not starting with a digit";
  return names.findIndex((n) => n === name) !== index ? "Another field has this name" : null;
}
