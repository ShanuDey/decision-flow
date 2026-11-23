import { failureResponse, type KeyIdentity, requireAction } from "./auth/api-key";
import { requiredAction } from "./auth/scopes";
import { triggerBody, triggerTarget } from "./auth/trigger";
import { errorResponse } from "./backend-proxy";
import { forwardToApi } from "./gateway";

export interface GatewayCall {
  method: string;
  path: string;
  search?: string;
  headers: Headers;
  body?: string | ReadableStream | null;
  signal?: AbortSignal;
}

// The one path for REST and MCP, so their allowlist and scope checks cannot differ.
export async function callGateway(call: GatewayCall, auth: KeyIdentity): Promise<Response> {
  const action = requiredAction(call.method, call.path);
  if (!action) return errorResponse(404, "not_found", "Not found");
  const denied = requireAction(auth.actions, action);
  if (denied) return failureResponse(denied);

  let target = call.path;
  let body = call.body ?? null;
  let headers = call.headers;
  const trigger = triggerTarget(call.path);
  if (trigger) {
    const parsed = triggerBody(body === null ? "" : await new Response(body).text());
    if (!parsed.ok) return errorResponse(422, "invalid_request", parsed.message);
    target = trigger;
    body = parsed.body;
    headers = new Headers(call.headers);
    headers.set("content-type", "application/json");
  }

  // Marks API-key callers; a client cannot send it.
  const extra: Record<string, string> = { "x-df-source": "api" };
  const external = call.headers.get("x-external-user-id");
  if (external) extra["x-external-user-id"] = external;

  const response = await forwardToApi(
    { method: call.method, path: target, search: call.search, headers, body, signal: call.signal },
    auth.user,
    extra,
  );
  response.headers.set("cache-control", "no-store");
  return response;
}
