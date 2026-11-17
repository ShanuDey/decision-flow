import type { ConnectionSummary, ConnectionTypeInfo, FieldInfo } from "@/lib/api/models";

export const NAME_MAX = 80;
export const VALUE_MAX = 4096;
export const SECRET_MIN = 8;

export interface ConnectionOption {
  id: string;
  name: string;
  typeName: string;
  hosts: string;
}

export function isUrl(value: string): boolean {
  try {
    const url = new URL(value.trim());
    return (url.protocol === "http:" || url.protocol === "https:") && url.hostname !== "";
  } catch {
    return false;
  }
}

export function fieldProblem(field: FieldInfo, value: string, editing: boolean): string | null {
  if (!value.trim()) {
    if ((field.secret && editing) || field.default) return null;
    return field.required ? `${field.label} is required` : null;
  }
  if (value.length > VALUE_MAX) return `${field.label} is too long`;
  if (field.format === "url" && !isUrl(value)) return `${field.label} must start with http:// or https://`;
  if (field.secret && value.length < SECRET_MIN) {
    return `${field.label} must be at least ${SECRET_MIN} characters`;
  }
  return null;
}

export function formProblem(
  type: ConnectionTypeInfo | undefined,
  name: string,
  values: Record<string, string>,
  editing: boolean,
): string | null {
  if (!type) return "Pick a type";
  if (!name.trim()) return "Enter a name";
  for (const field of type.fields) {
    const problem = fieldProblem(field, values[field.name] ?? "", editing);
    if (problem) return problem;
  }
  return null;
}

// A blank secret is left out when editing, so the saved value is kept.
export function payloadValues(
  type: ConnectionTypeInfo,
  values: Record<string, string>,
  editing: boolean,
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const field of type.fields) {
    const value = values[field.name] ?? "";
    if (field.secret) {
      if (value || !editing) out[field.name] = value;
    } else {
      out[field.name] = value.trim();
    }
  }
  return out;
}

export function hostsLabel(connection: ConnectionSummary, type: ConnectionTypeInfo | undefined): string {
  if (type && type.hosts.length > 0) return type.hosts.join(", ");
  if (type?.hosts_from) {
    const field = type.fields.find((f) => f.name === type.hosts_from);
    const base = connection.config[type.hosts_from] || field?.default || "";
    return isUrl(base) ? new URL(base.trim()).hostname : "";
  }
  return connection.config.hosts ?? "";
}

export interface TypeGroups {
  builtin: ConnectionTypeInfo[];
  custom: ConnectionTypeInfo[];
}

export function groupTypes(types: ConnectionTypeInfo[], query: string): TypeGroups {
  const needle = query.trim().toLowerCase();
  const shown = needle
    ? types.filter((t) => `${t.name} ${t.description}`.toLowerCase().includes(needle))
    : types;
  return {
    builtin: shown.filter((t) => t.category !== "custom"),
    custom: shown.filter((t) => t.category === "custom"),
  };
}

// Suggested name: the base URL's host once typed, else the type's name.
export function suggestName(
  type: ConnectionTypeInfo,
  values: Record<string, string>,
  existing: string[],
): string {
  const base = type.hosts_from ? (values[type.hosts_from] ?? "") : "";
  const stem = isUrl(base) ? new URL(base.trim()).hostname : type.name;
  const taken = new Set(existing.map((name) => name.trim().toLowerCase()));
  let name = stem;
  for (let n = 2; taken.has(name.toLowerCase()); n++) name = `${stem} ${n}`;
  return name.slice(0, NAME_MAX);
}

export function connectionOptions(
  connections: ConnectionSummary[],
  types: ConnectionTypeInfo[],
): ConnectionOption[] {
  const byId = new Map(types.map((t) => [t.id, t]));
  return connections.map((c) => {
    const type = byId.get(c.type);
    return { id: c.id, name: c.name, typeName: type?.name ?? c.type, hosts: hostsLabel(c, type) };
  });
}
