import { createMcpHandler } from "@modelcontextprotocol/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../auth/server", () => ({ getAuth: vi.fn(), getRuntime: vi.fn() }));
vi.mock("../gateway", () => ({ forwardToApi: vi.fn() }));

import type { KeyIdentity } from "../auth/api-key";
import { createMcpServer, type Gateway, TOOLS } from "./server";
import { MCP_OPERATIONS } from "./tools";

const identity: KeyIdentity = { user: { id: "user-1" }, actions: ["read", "write", "run"] };
const gateway = vi.fn<Gateway>();

const handler = createMcpHandler(() => createMcpServer(identity, gateway));

// A 2025-era client: no session, each request stands alone.
const send = (body: object) =>
  handler.fetch(
    new Request("http://test/mcp", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        accept: "application/json, text/event-stream",
        "mcp-protocol-version": "2025-06-18",
      },
      body: JSON.stringify(body),
    }),
  );

// Fields are only present on the replies that carry them; the tests read the ones they expect.
interface Reply {
  result: {
    tools: { name: string; description: string; inputSchema: { required: string[] }; annotations: Record<string, boolean> }[];
    content: { type: string; text: string }[];
    isError?: boolean;
    serverInfo: { name: string };
    instructions: string;
  };
  error?: { code: number; message: string };
}

async function rpc(method: string, params?: object): Promise<Reply> {
  const response = await send({ jsonrpc: "2.0", id: 1, method, params });
  const text = await response.text();
  const data = text.split("\n").find((line) => line.startsWith("data: "));
  return JSON.parse(data ? data.slice(6) : text) as Reply;
}

const call = (name: string, args: object) => rpc("tools/call", { name, arguments: args });
const json = (value: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(value), { status, headers });

beforeEach(() => gateway.mockReset());

describe("tools/list", () => {
  it("lists exactly the MCP subset, from the spec, without calling the API", async () => {
    const { result } = await rpc("tools/list");

    expect(result.tools.map((t: { name: string }) => t.name)).toEqual([...MCP_OPERATIONS]);
    expect(gateway).not.toHaveBeenCalled();
  });

  it("describes each tool with its schema and hints", async () => {
    const { result } = await rpc("tools/list");
    const save = result.tools.find((t) => t.name === "save_draft")!;

    expect(save.inputSchema.required).toEqual(expect.arrayContaining(["flow_id", "if_match", "draft"]));
    expect(save.annotations).toMatchObject({ idempotentHint: true });
    expect(save.description).toContain("If-Match");
  });

  it("matches the tool objects we built", async () => {
    const { result } = await rpc("tools/list");
    expect(result.tools).toHaveLength(TOOLS.length);
  });
});

describe("initialize", () => {
  it("introduces the server with instructions", async () => {
    const { result } = await rpc("initialize", {
      protocolVersion: "2025-06-18",
      capabilities: {},
      clientInfo: { name: "test", version: "1" },
    });
    expect(result.serverInfo.name).toBe("decision-flow");
    expect(result.instructions).toContain("list_flows");
  });
});

describe("tools/call", () => {
  it("calls the gateway as the key's owner and returns the body", async () => {
    gateway.mockResolvedValue(json({ items: [{ id: "f1" }], total: 1 }));

    const { result } = await call("list_flows", { q: "loan", page: 2 });

    expect(result.isError).toBeUndefined();
    expect(JSON.parse(result.content[0].text)).toEqual({ items: [{ id: "f1" }], total: 1 });
    const [sent, who] = gateway.mock.calls[0];
    expect(sent).toMatchObject({ method: "GET", path: "/flows" });
    expect(new URLSearchParams(sent.search).get("q")).toBe("loan");
    expect(who).toBe(identity);
  });

  it("sends a saved draft with its version", async () => {
    gateway.mockResolvedValue(json({ draft_version: 4 }));

    await call("save_draft", { flow_id: "f1", if_match: 3, draft: { nodes: [] } });

    const [sent] = gateway.mock.calls[0];
    expect(sent).toMatchObject({ method: "PUT", path: "/flows/f1/draft", body: '{"nodes":[]}' });
    expect(sent.headers.get("if-match")).toBe("3");
  });

  it("refuses a missing argument without calling the API", async () => {
    const { result } = await call("get_flow", {});

    expect(result.isError).toBe(true);
    expect(result.content[0].text).toBe("Missing required argument: flow_id.");
    expect(gateway).not.toHaveBeenCalled();
  });

  it("refuses an id that could change the route without calling the API", async () => {
    for (const flow_id of ["..", "a/b", { x: 1 }]) {
      const { result } = await call("get_flow", { flow_id });
      expect(result.isError, JSON.stringify(flow_id)).toBe(true);
    }
    const { result } = await call("get_flow", { flow_id: "f1", extra: 1 });
    expect(result.isError).toBe(true);
    expect(gateway).not.toHaveBeenCalled();
  });

  it("explains a validation failure so the agent can fix the graph", async () => {
    gateway.mockResolvedValue(
      json(
        { code: "invalid_flow", message: "End needs a value", details: { errors: [{ node_id: "end", field: "outputs.0.value", message: "End needs a value" }] } },
        422,
      ),
    );

    const { result } = await call("validate_flow", { flow_id: "f1" });

    expect(result.isError).toBe(true);
    expect(result.content[0].text).toContain("invalid_flow: End needs a value");
    expect(result.content[0].text).toContain("- end / outputs.0.value");
  });

  it("names the missing scope when the gateway refuses", async () => {
    gateway.mockResolvedValue(json({ code: "insufficient_scope", message: 'This key does not have the "write" scope', details: {} }, 403));

    const { result } = await call("publish_flow", { flow_id: "f1" });

    expect(result.isError).toBe(true);
    expect(result.content[0].text).toContain('insufficient_scope: This key does not have the "write" scope');
  });

  it("tells the agent to retry when the API is starting up", async () => {
    gateway.mockResolvedValue(
      json({ code: "upstream_unavailable", message: "The service is starting up or unavailable.", details: {} }, 502, { "retry-after": "30" }),
    );

    const { result } = await call("list_flows", {});

    expect(result.isError).toBe(true);
    expect(result.content[0].text).toContain("starting up");
    expect(result.content[0].text).toContain("Retry after about 30 seconds.");
  });

  it("answers an unknown tool with a protocol error", async () => {
    const { error } = await call("delete_flow", { flow_id: "f1" });
    expect(error).toBeDefined();
    expect(gateway).not.toHaveBeenCalled();
  });
});

describe("other methods", () => {
  it("has no session stream to open or close", async () => {
    for (const method of ["GET", "DELETE"]) {
      const response = await handler.fetch(new Request("http://test/mcp", { method }));
      expect(response.status, method).toBe(405);
    }
  });
});
