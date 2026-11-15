export const KEY_PREFIX = "df_live_";

export const RESOURCE = "flows";
export const ACTIONS = ["read", "write", "run"] as const;
export type Action = (typeof ACTIONS)[number];

export type Permissions = Record<string, string[]>;

export function permissionsFor(actions: readonly Action[]): Permissions {
  return { [RESOURCE]: ACTIONS.filter((action) => actions.includes(action)) };
}

export const FULL_ACCESS: Permissions = permissionsFor(ACTIONS);

// Actions are independent: "write" does not imply "read".
export function hasAction(permissions: Permissions | null | undefined, action: Action): boolean {
  return permissions?.[RESOURCE]?.includes(action) === true;
}

const ID = "[^/]+";
const route = (method: string, pattern: string, action: Action) => ({
  method,
  pattern: new RegExp(`^${pattern}$`),
  action,
});

// Default deny: a route not listed here is unreachable with a key.
const ROUTES = [
  route("GET", "/flows", "read"),
  route("GET", `/flows/${ID}`, "read"),
  route("GET", `/flows/${ID}/versions`, "read"),
  route("GET", `/flows/${ID}/versions/\\d+`, "read"),
  route("POST", `/flows/${ID}/validate`, "read"),
  route("GET", "/runs", "read"),
  route("GET", `/runs/${ID}`, "read"),
  route("GET", `/runs/${ID}/steps`, "read"),
  route("POST", "/flows", "write"),
  route("PATCH", `/flows/${ID}`, "write"),
  route("DELETE", `/flows/${ID}`, "write"),
  route("PUT", `/flows/${ID}/draft`, "write"),
  route("POST", `/flows/${ID}/publish`, "write"),
  route("POST", `/flows/${ID}/runs`, "run"),
];

export function requiredAction(method: string, path: string): Action | null {
  const verb = method.toUpperCase();
  return ROUTES.find((r) => r.method === verb && r.pattern.test(path))?.action ?? null;
}
