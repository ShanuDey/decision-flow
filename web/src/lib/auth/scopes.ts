export const KEY_PREFIX = "df_live_";

export const ACTIONS = [
  "flows:read",
  "flows:write",
  "flows:run",
  "agents:read",
  "agents:chat",
  "agents:manage",
] as const;
export type Action = (typeof ACTIONS)[number];

export const FLOW_ACTIONS = ["flows:read", "flows:write", "flows:run"] as const satisfies readonly Action[];

export type Permissions = Record<string, string[]>;

const split = (action: Action): [string, string] => {
  const [resource = "", name = ""] = action.split(":");
  return [resource, name];
};

export function permissionsFor(actions: readonly Action[]): Permissions {
  const permissions: Permissions = {};
  for (const action of ACTIONS.filter((a) => actions.includes(a))) {
    const [resource, name] = split(action);
    (permissions[resource] ??= []).push(name);
  }
  return permissions;
}

export const FULL_ACCESS: Permissions = permissionsFor(ACTIONS);

// Actions are independent: "write" does not imply "read".
export function hasAction(permissions: Permissions | null | undefined, action: Action): boolean {
  const [resource, name] = split(action);
  return permissions?.[resource]?.includes(name) === true;
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
  route("GET", "/flows", "flows:read"),
  route("GET", "/flow-format", "flows:read"),
  route("GET", "/flows/{flow_id}", "flows:read"),
  route("GET", "/flows/{flow_id}/versions", "flows:read"),
  route("GET", "/flows/{flow_id}/versions/{version}", "flows:read"),
  route("POST", "/flows/{flow_id}/validate", "flows:read"),
  route("GET", "/runs", "flows:read"),
  route("GET", "/runs/{run_id}", "flows:read"),
  route("GET", "/runs/{run_id}/steps", "flows:read"),
  route("POST", "/flows", "flows:write"),
  route("PATCH", "/flows/{flow_id}", "flows:write"),
  route("DELETE", "/flows/{flow_id}", "flows:write"),
  route("PUT", "/flows/{flow_id}/draft", "flows:write"),
  route("POST", "/flows/{flow_id}/publish", "flows:write"),
  route("POST", "/flows/{flow_id}/runs", "flows:run"),
  route("POST", "/flows/{flow_id}/trigger", "flows:run"),
  route("GET", "/agents", "agents:read"),
  route("GET", "/agents/{agent_id}", "agents:read"),
  route("GET", "/agents/{agent_id}/threads", "agents:read"),
  route("GET", "/agents/{agent_id}/threads/{thread_id}", "agents:read"),
  route("GET", "/agents/{agent_id}/threads/{thread_id}/messages/{message_id}/steps", "agents:read"),
  route("POST", "/agents/{agent_id}/threads", "agents:chat"),
  route("DELETE", "/agents/{agent_id}/threads/{thread_id}", "agents:chat"),
  route("POST", "/agents/{agent_id}/threads/{thread_id}/messages", "agents:chat"),
  route("POST", "/agents/{agent_id}/invoke", "agents:chat"),
  route("POST", "/agents", "agents:manage"),
  route("PATCH", "/agents/{agent_id}", "agents:manage"),
  route("DELETE", "/agents/{agent_id}", "agents:manage"),
];

export function requiredAction(method: string, path: string): Action | null {
  const verb = method.toUpperCase();
  return GATEWAY_ROUTES.find((r) => r.method === verb && r.pattern.test(path))?.action ?? null;
}
