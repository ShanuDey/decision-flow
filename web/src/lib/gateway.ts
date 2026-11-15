import { type TokenUser } from "./auth/api-token";
import { getConfig } from "./auth/server";
import { apiToken } from "./auth/session";
import {
  API_TIMEOUT_MS,
  errorResponse,
  hasBody,
  responseHeaders,
  upstreamHeaders,
} from "./backend-proxy";

export interface ApiCall {
  method: string;
  path: string;
  search?: string;
  headers: Headers;
  body?: ReadableStream | null;
  signal?: AbortSignal;
}

// The caller must already have authenticated `user`.
export async function forwardToApi(call: ApiCall, user: TokenUser): Promise<Response> {
  const { apiUrl, ipHeader } = getConfig();
  const timeout = AbortSignal.timeout(API_TIMEOUT_MS);
  const init: RequestInit & { duplex?: "half" } = {
    method: call.method,
    headers: upstreamHeaders(call.headers, await apiToken(user), ipHeader),
    redirect: "manual",
    signal: call.signal ? AbortSignal.any([call.signal, timeout]) : timeout,
  };
  if (hasBody(call.method) && call.body) {
    init.body = call.body;
    init.duplex = "half";
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${apiUrl}${call.path}${call.search ?? ""}`, init);
  } catch {
    return errorResponse(502, "upstream_unavailable", "The service is unavailable");
  }
  const empty = upstream.status === 204 || upstream.status === 304;
  return new Response(empty ? null : upstream.body, {
    status: upstream.status,
    headers: responseHeaders(upstream.headers, apiUrl),
  });
}
