import { authenticateKey, failureResponse } from "@/lib/auth/api-key";
import { requiredAction } from "@/lib/auth/scopes";
import { errorResponse, upstreamPath } from "@/lib/backend-proxy";
import { callGateway } from "@/lib/gateway-v1";

export const maxDuration = 60;

type Context = { params: Promise<{ path: string[] }> };

// Cookies are never read here, so no Origin check is needed.
async function handle(request: Request, { params }: Context): Promise<Response> {
  const path = upstreamPath((await params).path);
  if (!path || !requiredAction(request.method, path)) return errorResponse(404, "not_found", "Not found");

  const auth = await authenticateKey(request.headers);
  if (!auth.ok) return failureResponse(auth);

  return callGateway(
    {
      method: request.method,
      path,
      search: new URL(request.url).search,
      headers: request.headers,
      body: request.body,
      signal: request.signal,
    },
    auth,
  );
}

export { handle as DELETE, handle as GET, handle as PATCH, handle as POST, handle as PUT };
