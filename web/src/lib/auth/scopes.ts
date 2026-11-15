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

const route = (method: string, template: string, action: Action) => ({
  method,
  template,
  pattern: new RegExp(
    `^${template.replace("{version}", "\\d+").replace(/\{[^}]+\}/g, "[^/]+")}$`,
  ),
  action,
});

// Default deny: a route not listed here is unreachable with a key. Param names match the API spec.
export const GATEWAY_ROUTES = [
  route("GET", "/flows", "read"),
  route("GET", "/flow-format", "read"),
  route("GET", "/flows/{flow_id}", "read"),
  route("GET", "/flows/{flow_id}/versions", "read"),
  route("GET", "/flows/{flow_id}/versions/{version}", "read"),
  route("POST", "/flows/{flow_id}/validate", "read"),
  route("GET", "/runs", "read"),
  route("GET", "/runs/{run_id}", "read"),
  route("GET", "/runs/{run_id}/steps", "read"),
  route("POST", "/flows", "write"),
  route("PATCH", "/flows/{flow_id}", "write"),
  route("DELETE", "/flows/{flow_id}", "write"),
  route("PUT", "/flows/{flow_id}/draft", "write"),
  route("POST", "/flows/{flow_id}/publish", "write"),
  route("POST", "/flows/{flow_id}/runs", "run"),
  route("POST", "/flows/{flow_id}/trigger", "run"),
];

export function requiredAction(method: string, path: string): Action | null {
  const verb = method.toUpperCase();
  return GATEWAY_ROUTES.find((r) => r.method === verb && r.pattern.test(path))?.action ?? null;
}
