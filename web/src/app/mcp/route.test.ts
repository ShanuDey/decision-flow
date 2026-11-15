import { beforeEach, describe, expect, it, vi } from "vitest";

const verifyApiKey = vi.hoisted(() => vi.fn());
const query = vi.hoisted(() => vi.fn());
const callGateway = vi.hoisted(() => vi.fn());
const wakeApi = vi.hoisted(() => vi.fn());

vi.mock("@/lib/auth/server", () => ({
  getAuth: () => ({ api: { verifyApiKey } }),
  getRuntime: () => ({ pool: { query } }),
}));
vi.mock("@/lib/gateway-v1", () => ({ callGateway }));
vi.mock("@/lib/gateway", () => ({ forwardToApi: vi.fn() }));
vi.mock("@/lib/wake", () => ({ wakeApi }));

import * as route from "./route";

const KEY = `df_live_${"b".repeat(64)}`;
const owner = { id: "user-1", email: "a@acme.com", emailVerified: true, name: "Alex" };

function post(body: object, authorization: string | null = `Bearer ${KEY}`): Request {
  return new Request("http://test/mcp", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      accept: "application/json, text/event-stream",
      "mcp-protocol-version": "2025-06-18",
      ...(authorization && { authorization }),
    },
    body: JSON.stringify(body),
  });
}

async function result(response: Response) {
  const text = await response.text();
  const data = text.split("\n").find((line) => line.startsWith("data: "));
  return JSON.parse(data ? data.slice(6) : text);
}

beforeEach(() => {
  verifyApiKey.mockReset();
  query.mockReset();
  callGateway.mockReset();
  wakeApi.mockReset();
  verifyApiKey.mockResolvedValue({
    valid: true,
    error: null,
    key: { referenceId: "user-1", permissions: { flows: ["read", "run"] } },
  });
  query.mockResolvedValue({ rows: [owner] });
});

describe("POST /mcp", () => {
  it("rejects a request without a key before touching the API or the SDK", async () => {
    const response = await route.POST(post({ jsonrpc: "2.0", id: 1, method: "tools/list" }, null));

    expect(response.status).toBe(401);
    expect(response.headers.get("www-authenticate")).toBe("Bearer");
    expect((await response.json()).code).toBe("missing_key");
    expect(wakeApi).not.toHaveBeenCalled();
  });

  it("rejects a revoked or expired key", async () => {
    verifyApiKey.mockResolvedValue({ valid: false, error: { code: "KEY_EXPIRED" }, key: null });

    const response = await route.POST(post({ jsonrpc: "2.0", id: 1, method: "tools/list" }));

    expect(response.status).toBe(401);
    expect((await response.json()).code).toBe("key_expired");
  });

  it("passes a rate limit through with Retry-After", async () => {
    verifyApiKey.mockResolvedValue({ valid: false, error: { code: "RATE_LIMITED", details: { tryAgainIn: 4000 } }, key: null });

    const response = await route.POST(post({ jsonrpc: "2.0", id: 1, method: "tools/list" }));

    expect(response.status).toBe(429);
    expect(response.headers.get("retry-after")).toBe("4");
  });

  it("lists the tools and starts waking the API", async () => {
    const response = await route.POST(post({ jsonrpc: "2.0", id: 1, method: "tools/list" }));

    expect(response.status).toBe(200);
    const body = await result(response);
    expect(body.result.tools.map((t: { name: string }) => t.name)).toContain("list_flows");
    expect(wakeApi).toHaveBeenCalledTimes(1);
    expect(callGateway).not.toHaveBeenCalled();
  });

  it("verifies the key once per request, not once per tool", async () => {
    callGateway.mockResolvedValue(Response.json({ items: [] }));

    await route.POST(post({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name: "list_flows", arguments: {} } }));

    expect(verifyApiKey).toHaveBeenCalledTimes(1);
  });

  it("hands the key's owner and actions to the gateway on a tool call", async () => {
    callGateway.mockResolvedValue(Response.json({ items: [] }));

    const response = await route.POST(
      post({ jsonrpc: "2.0", id: 2, method: "tools/call", params: { name: "list_flows", arguments: { q: "loan" } } }),
    );

    const body = await result(response);
    expect(body.result.isError).toBeUndefined();
    expect(JSON.parse(body.result.content[0].text)).toEqual({ items: [] });
    const [call, identity] = callGateway.mock.calls[0];
    expect(call).toMatchObject({ method: "GET", path: "/flows", search: "?q=loan" });
    expect(identity).toEqual({ user: owner, actions: ["read", "run"] });
  });

  it("shows a scope refusal from the gateway as a tool error", async () => {
    callGateway.mockResolvedValue(
      Response.json({ code: "insufficient_scope", message: 'This key does not have the "write" scope', details: {} }, { status: 403 }),
    );

    const response = await route.POST(
      post({ jsonrpc: "2.0", id: 3, method: "tools/call", params: { name: "publish_flow", arguments: { flow_id: "f1" } } }),
    );

    const body = await result(response);
    expect(body.result.isError).toBe(true);
    expect(body.result.content[0].text).toContain("insufficient_scope");
  });

  it("only serves POST", () => {
    expect(Object.keys(route).filter((name) => ["GET", "DELETE", "PUT", "PATCH"].includes(name))).toEqual([]);
  });
});
