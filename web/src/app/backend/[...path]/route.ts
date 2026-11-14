import {
  errorResponse,
  hasBody,
  isAllowedOrigin,
  isSafeMethod,
  responseHeaders,
  upstreamHeaders,
  upstreamPath,
} from "@/lib/backend-proxy";
import { getConfig } from "@/lib/auth/server";
import { apiToken, currentSession } from "@/lib/auth/session";

type Context = { params: Promise<{ path: string[] }> };

async function handle(request: Request, { params }: Context): Promise<Response> {
  const { apiUrl, baseURL, trustedOrigins, ipHeader } = getConfig();

  if (!isSafeMethod(request.method) && !isAllowedOrigin(request.headers.get("origin"), baseURL, trustedOrigins)) {
    return errorResponse(403, "forbidden_origin", "Cross-origin request refused");
  }
  const path = upstreamPath((await params).path);
  if (!path) return errorResponse(404, "not_found", "Not found");

  const session = await currentSession();
  if (!session) return errorResponse(401, "session_expired", "Sign in required");

  const search = new URL(request.url).search;
  const init: RequestInit & { duplex?: "half" } = {
    method: request.method,
    headers: upstreamHeaders(request.headers, await apiToken(session.user), ipHeader),
    redirect: "manual",
    signal: request.signal,
  };
  if (hasBody(request.method) && request.body) {
    init.body = request.body;
    init.duplex = "half";
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${apiUrl}${path}${search}`, init);
  } catch {
    return errorResponse(502, "upstream_unavailable", "The service is unavailable");
  }
  const empty = upstream.status === 204 || upstream.status === 304;
  return new Response(empty ? null : upstream.body, {
    status: upstream.status,
    headers: responseHeaders(upstream.headers, apiUrl),
  });
}

export { handle as DELETE, handle as GET, handle as PATCH, handle as POST, handle as PUT };
