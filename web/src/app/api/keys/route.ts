import { errorResponse, isAllowedOrigin } from "@/lib/backend-proxy";
import { createKeyBody, expiresInSeconds, MAX_KEYS } from "@/lib/auth/key-request";
import { permissionsFor } from "@/lib/auth/scopes";
import { getAuth, getConfig } from "@/lib/auth/server";
import { currentSession } from "@/lib/auth/session";

export async function POST(request: Request): Promise<Response> {
  const { baseURL, trustedOrigins } = getConfig();
  if (!isAllowedOrigin(request.headers.get("origin"), baseURL, trustedOrigins)) {
    return errorResponse(403, "forbidden_origin", "Cross-origin request refused");
  }
  const session = await currentSession();
  if (!session) return errorResponse(401, "session_expired", "Sign in required");

  const body = createKeyBody.safeParse(await request.json().catch(() => null));
  if (!body.success) return errorResponse(422, "invalid_request", "Check the name, scopes and expiry");

  const auth = getAuth();
  const { total } = await auth.api.listApiKeys({ headers: request.headers });
  if (total >= MAX_KEYS) {
    return errorResponse(409, "key_limit_reached", `You can have up to ${MAX_KEYS} keys. Revoke one first.`);
  }

  // No headers here: the plugin refuses permissions on calls that carry request headers.
  const created = await auth.api.createApiKey({
    body: {
      name: body.data.name,
      userId: session.user.id,
      permissions: permissionsFor(body.data.actions),
      expiresIn: expiresInSeconds(body.data.expiresInDays),
    },
  });

  return Response.json(
    {
      id: created.id,
      name: created.name,
      key: created.key,
      start: created.start,
      expiresAt: created.expiresAt,
    },
    { status: 201, headers: { "cache-control": "no-store" } },
  );
}
