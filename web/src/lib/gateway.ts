import { type TokenUser } from "./auth/api-token";
import { getConfig } from "./auth/server";
import { apiToken } from "./auth/session";
import {
  RELAY_TIMEOUT_MS,
  hasBody,
  responseHeaders,
  upstreamHeaders,
  upstreamUnavailable,
} from "./backend-proxy";
import { wakeApi } from "./wake";

export interface ApiCall {
  method: string;
  path: string;
  search?: string;
  headers: Headers;
  body?: BodyInit | null;
  signal?: AbortSignal;
}

// The caller must already have authenticated `user`. `extra` headers are set by us, never by the client.
export async function forwardToApi(
  call: ApiCall,
  user: TokenUser,
  extra: Record<string, string> = {},
): Promise<Response> {
  const { apiUrl, ipHeader } = getConfig();
  const timeout = AbortSignal.timeout(RELAY_TIMEOUT_MS);
  const headers = upstreamHeaders(call.headers, await apiToken(user), ipHeader);
  for (const [name, value] of Object.entries(extra)) headers.set(name, value);
  const init: RequestInit & { duplex?: "half" } = {
    method: call.method,
    headers,
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
    wakeApi();
    return upstreamUnavailable();
  }
  const empty = upstream.status === 204 || upstream.status === 304;
  return new Response(empty ? null : upstream.body, {
    status: upstream.status,
    headers: responseHeaders(upstream.headers, apiUrl),
  });
}
