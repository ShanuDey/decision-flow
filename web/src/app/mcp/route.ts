import { createMcpHandler } from "@modelcontextprotocol/server";

import { authenticateKey, failureResponse, type KeyIdentity } from "@/lib/auth/api-key";
import { createMcpServer } from "@/lib/mcp/server";
import { wakeApi } from "@/lib/wake";

export const maxDuration = 60;

const handler = createMcpHandler((ctx) => {
  const identity = ctx.authInfo?.extra?.identity as KeyIdentity | undefined;
  if (!identity) throw new Error("MCP request reached the server without an authenticated key");
  return createMcpServer(identity);
});

// POST only: stateless, so there is no session stream to open or close.
export async function POST(request: Request): Promise<Response> {
  const auth = await authenticateKey(request.headers);
  if (!auth.ok) return failureResponse(auth);

  wakeApi();
  const { user, actions } = auth;
  return handler.fetch(request, {
    authInfo: {
      token: "api-key",
      clientId: user.id,
      scopes: actions,
      extra: { identity: { user, actions } satisfies KeyIdentity },
    },
  });
}
