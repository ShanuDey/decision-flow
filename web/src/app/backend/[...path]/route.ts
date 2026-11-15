import { errorResponse, isAllowedOrigin, isSafeMethod, upstreamPath } from "@/lib/backend-proxy";
import { getConfig } from "@/lib/auth/server";
import { currentSession } from "@/lib/auth/session";
import { forwardToApi } from "@/lib/gateway";

export const maxDuration = 60;

type Context = { params: Promise<{ path: string[] }> };

async function handle(request: Request, { params }: Context): Promise<Response> {
  const { baseURL, trustedOrigins } = getConfig();

  if (!isSafeMethod(request.method) && !isAllowedOrigin(request.headers.get("origin"), baseURL, trustedOrigins)) {
    return errorResponse(403, "forbidden_origin", "Cross-origin request refused");
  }
  const path = upstreamPath((await params).path);
  if (!path) return errorResponse(404, "not_found", "Not found");

  const session = await currentSession();
  if (!session) return errorResponse(401, "session_expired", "Sign in required");

  return forwardToApi(
    {
      method: request.method,
      path,
      search: new URL(request.url).search,
      headers: request.headers,
      body: request.body,
      signal: request.signal,
    },
    session.user,
  );
}

export { handle as DELETE, handle as GET, handle as PATCH, handle as POST, handle as PUT };
