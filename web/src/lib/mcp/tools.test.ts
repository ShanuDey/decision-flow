import { describe, expect, it } from "vitest";

import { requiredAction } from "../auth/scopes";
import publicSpec from "../docs/public-openapi.json";
import type { OpenApiDoc } from "../docs/public-spec";
import { buildTools, MCP_OPERATIONS } from "./tools";

const spec = publicSpec as unknown as OpenApiDoc;
const tools = buildTools(spec);
const tool = (name: string) => tools.find((t) => t.name === name)!;

describe("buildTools", () => {
  it("builds exactly the listed operations, in order", () => {
    expect(tools.map((t) => t.name)).toEqual([...MCP_OPERATIONS]);
    expect(new Set(tools.map((t) => t.name)).size).toBe(tools.length);
  });

  it("keeps REST-only operations out", () => {
    for (const name of ["delete_flow", "rename_flow", "list_versions", "get_version", "trigger_flow"]) {
      expect(tools.map((t) => t.name)).not.toContain(name);
    }
  });

  it("fails loudly when an operation is not in the spec", () => {
    expect(() => buildTools(spec, ["list_flows", "nope"])).toThrow(/nope/);
  });

  it("gives every tool a description, an object schema and no unresolved refs", () => {
    for (const t of tools) {
      expect(t.description.length, t.name).toBeGreaterThan(20);
      expect(t.inputSchema.type, t.name).toBe("object");
      expect(t.inputSchema.additionalProperties, t.name).toBe(false);
      expect(JSON.stringify(t.inputSchema), t.name).not.toContain("$ref");
    }
  });

  it("only builds requests the gateway allows, with the scope the tool declares", () => {
    for (const t of tools) {
      const args = Object.fromEntries(
        (t.inputSchema.required as string[]).map((key) => [key, key === "flow_id" || key === "run_id" ? "id-1" : key === "if_match" ? 1 : { a: 1 }]),
      );
      const { method, path } = t.request(args);
      expect(requiredAction(method, path), t.name).toBe(t.action);
    }
  });
});

describe("annotations", () => {
  it("marks reads as read-only", () => {
    for (const name of ["list_flows", "get_flow", "get_flow_format", "validate_flow", "list_runs", "get_run", "get_run_steps"]) {
      expect(tool(name).annotations).toMatchObject({ readOnlyHint: true });
    }
  });

  it("marks saving a draft as an idempotent overwrite and creating things as additive", () => {
    expect(tool("save_draft").annotations).toMatchObject({ destructiveHint: true, idempotentHint: true });
    for (const name of ["create_flow", "publish_flow", "create_run"]) {
      expect(tool(name).annotations).toMatchObject({ destructiveHint: false, idempotentHint: false });
    }
  });
});

describe("save_draft", () => {
  const save = tool("save_draft");

  it("needs the flow, the draft version and the graph", () => {
    expect(save.inputSchema.required).toEqual(expect.arrayContaining(["flow_id", "if_match", "draft"]));
    expect(save.missing({ flow_id: "a" })).toEqual(["if_match", "draft"]);
    expect(save.missing({ flow_id: "a", if_match: 0, draft: {} })).toEqual([]);
  });

  it("explains the graph argument", () => {
    const draft = (save.inputSchema.properties as Record<string, { description?: string }>).draft;
    expect(draft.description).toContain("flow graph");
  });

  it("sends the graph as the body and the version as If-Match", () => {
    const request = save.request({ flow_id: "abc", if_match: 3, draft: { nodes: [], edges: [] } });
    expect(request.method).toBe("PUT");
    expect(request.path).toBe("/flows/abc/draft");
    expect(request.headers.get("if-match")).toBe("3");
    expect(request.headers.get("content-type")).toBe("application/json");
    expect(JSON.parse(request.body!)).toEqual({ nodes: [], edges: [] });
    expect(request.search).toBe("");
  });
});

describe("create_run", () => {
  const run = tool("create_run");

  it("flattens the body into arguments and explains the test flag", () => {
    const properties = run.inputSchema.properties as Record<string, { description?: string }>;
    expect(Object.keys(properties).sort()).toEqual(["flow_id", "input", "test"]);
    expect(properties.test.description).toContain("draft");
    expect(run.inputSchema.required).toEqual(["flow_id"]);
  });

  it("sends only the body fields that were given", () => {
    expect(JSON.parse(run.request({ flow_id: "f", input: { amount: 5 } }).body!)).toEqual({ input: { amount: 5 } });
    expect(JSON.parse(run.request({ flow_id: "f", test: true }).body!)).toEqual({ test: true });
  });
});

describe("check", () => {
  const get = tool("get_flow");

  it("accepts ordinary arguments", () => {
    expect(get.check({ flow_id: "f1" })).toBeNull();
    expect(tool("save_draft").check({ flow_id: "f1", if_match: 3, draft: { nodes: [] } })).toBeNull();
    expect(tool("list_runs").check({ flow_id: null, limit: 10 })).toBeNull();
  });

  it("refuses ids that could change the route", () => {
    for (const bad of ["..", ".", "", "a/b", "a\\b"]) {
      expect(get.check({ flow_id: bad }), bad).toMatch(/not a valid id/);
    }
  });

  it("refuses a non-scalar id", () => {
    expect(get.check({ flow_id: { a: 1 } })).toMatch(/flow_id/);
    expect(get.check({ flow_id: ["a"] })).toMatch(/flow_id/);
  });

  it("refuses unknown arguments and wrongly typed body fields", () => {
    expect(get.check({ flow_id: "f1", extra: 1 })).toBe("Unknown argument: extra.");
    expect(tool("create_run").check({ flow_id: "f1", input: "text" })).toMatch(/input/);
    expect(tool("save_draft").check({ flow_id: "f1", if_match: 1, draft: [] })).toMatch(/draft/);
  });
});

describe("list tools", () => {
  it("turns arguments into a query string and sends no body", () => {
    const request = tool("list_flows").request({ q: "loan", page: 2, page_size: 10 });
    expect(request.path).toBe("/flows");
    expect(new URLSearchParams(request.search).get("q")).toBe("loan");
    expect(new URLSearchParams(request.search).get("page")).toBe("2");
    expect(request.body).toBeUndefined();
    expect(request.headers.has("content-type")).toBe(false);
  });

  it("omits unset and null arguments", () => {
    expect(tool("list_runs").request({ flow_id: null, status: undefined }).search).toBe("");
  });

  it("encodes path values so an id cannot change the route", () => {
    expect(tool("get_run").request({ run_id: "a/b?c" }).path).toBe("/runs/a%2Fb%3Fc");
  });
});
