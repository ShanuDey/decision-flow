import { authenticateKey, failureResponse } from "@/lib/auth/api-key";
import { requiredAction } from "@/lib/auth/scopes";
import { errorResponse, upstreamPath } from "@/lib/backend-proxy";
import { forwardToApi } from "@/lib/gateway";

export const maxDuration = 60;

type Context = { params: Promise<{ path: string[] }> };

// Cookies are never read here, so no Origin check is needed.
async function handle(request: Request, { params }: Context): Promise<Response> {
  const path = upstreamPath((await params).path);
  const action = path && requiredAction(request.method, path);
  if (!path || !action) return errorResponse(404, "not_found", "Not found");

  const auth = await authenticateKey(request.headers, action);
  if (!auth.ok) return failureResponse(auth);

  const response = await forwardToApi(
    {
      method: request.method,
      path,
      search: new URL(request.url).search,
      headers: request.headers,
      body: request.body,
      signal: request.signal,
    },
    auth.user,
  );
  response.headers.set("cache-control", "no-store");
  return response;
}

export { handle as DELETE, handle as GET, handle as PATCH, handle as POST, handle as PUT };
