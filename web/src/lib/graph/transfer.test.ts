import { describe, expect, it } from "vitest";

import type { Graph } from "./types";
import {
  applyConnections,
  buildFlowFile,
  type ConnectionRef,
  flowFileName,
  MAX_IMPORT_BYTES,
  parseFlowFile,
  planConnections,
  usedConnectionIds,
} from "./transfer";

const graph = (nodes: unknown[] = []): Graph =>
  ({ schema_version: 1, variables: [], nodes, edges: [] }) as unknown as Graph;

const subflow = (id: string, flowId: string) => ({
  id,
  type: "subflow",
  name: "Call",
  position: { x: 0, y: 0 },
  data: { flow_id: flowId, inputs: { a: "{{ input.a }}" } },
});

describe("flowFileName", () => {
  it("makes a safe file name", () => {
    expect(flowFileName("Loan / Eligibility v2!")).toBe("loan-eligibility-v2.flow.json");
  });

  it("falls back when nothing is left", () => {
    expect(flowFileName("***")).toBe("flow.flow.json");
  });
});

describe("parseFlowFile", () => {
  it("round-trips an exported file", () => {
    const g = graph();
    const result = parseFlowFile(JSON.stringify(buildFlowFile("My flow", g)));
    expect(result).toEqual({ ok: true, name: "My flow", graph: g, clearedSubflows: 0, connections: {} });
  });

  it("accepts a bare graph with no name", () => {
    const result = parseFlowFile(JSON.stringify(graph()));
    expect(result).toMatchObject({ ok: true, name: null });
  });

  it("clears subflow ids and counts them", () => {
    const g = graph([subflow("s1", "5b0f0f1e-0000-4000-8000-000000000001"), subflow("s2", "")]);
    const result = parseFlowFile(JSON.stringify(buildFlowFile("x", g)));
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.clearedSubflows).toBe(1);
    const first = result.graph.nodes[0];
    expect(first.type === "subflow" && first.data.flow_id).toBe("");
    expect(first.type === "subflow" && first.data.inputs).toEqual({ a: "{{ input.a }}" });
  });

  it.each([
    ["not json", "{"],
    ["a number", "3"],
    ["a null", "null"],
    ["a graph with no nodes", JSON.stringify({ schema_version: 1 })],
    ["a wrong schema version", JSON.stringify({ schema_version: 2, nodes: [], edges: [] })],
    ["a wrapper with no graph", JSON.stringify({ format: "decision-flow.flow", version: 1 })],
  ])("rejects %s", (_label, text) => {
    expect(parseFlowFile(text).ok).toBe(false);
  });

  it("rejects a newer file version", () => {
    const text = JSON.stringify({ format: "decision-flow.flow", version: 2, graph: graph() });
    expect(parseFlowFile(text)).toMatchObject({ ok: false });
  });

  it("rejects an oversized file before parsing", () => {
    expect(parseFlowFile(" ".repeat(MAX_IMPORT_BYTES + 1))).toMatchObject({
      ok: false,
      message: "The file is too large to import.",
    });
  });
});

const request = (id: string, connectionId: string) => ({
  id,
  type: "http_request",
  name: "Call",
  position: { x: 0, y: 0 },
  data: {
    method: "GET",
    url: "https://api.github.com/user",
    headers: {},
    query: {},
    body_type: "none",
    body: null,
    timeout_seconds: null,
    fail_on_error_status: true,
    connection_id: connectionId,
  },
});

const ref = (id: string, name: string, typeId: string): ConnectionRef => ({ id, name, typeId });
const idOf = (g: Graph, index: number) => {
  const node = g.nodes[index];
  return node.type === "http_request" || node.type === "prompt" ? node.data.connection_id : undefined;
};

const prompt = (id: string, connectionId: string) => ({
  id,
  type: "prompt",
  name: "Ask",
  position: { x: 0, y: 0 },
  data: {
    connection_id: connectionId,
    model: "",
    system: "",
    prompt: "Hi",
    temperature: null,
    max_tokens: null,
    timeout_seconds: null,
  },
});

describe("connections in a file", () => {
  const g = graph([request("a", "c1"), request("b", "c1"), request("c", "c2"), request("d", "")]);
  const mine = [ref("c1", "prod-gh", "github"), ref("c9", "other", "slack")];

  it("lists each used connection once and skips empty ones", () => {
    expect(usedConnectionIds(g)).toEqual(["c1", "c2"]);
  });

  it("exports only the type and name of the connections a flow uses", () => {
    const file = buildFlowFile("x", g, mine);
    expect(file.connections).toEqual({ c1: { type: "github", name: "prod-gh" } });
    expect(JSON.stringify(file)).not.toContain("slack");
  });

  it("leaves the field out when no known connection is used", () => {
    expect("connections" in buildFlowFile("x", graph([request("a", "")]), mine)).toBe(false);
    expect("connections" in buildFlowFile("x", g)).toBe(false);
  });

  it("reads the hints back and ignores malformed ones", () => {
    const text = JSON.stringify({
      ...buildFlowFile("x", g, mine),
      connections: {
        c1: { type: "github", name: "prod-gh" },
        bad1: { type: 1, name: "x" },
        bad2: "nope",
        ["z".repeat(65)]: { type: "github", name: "x" },
        long: { type: "github", name: "n".repeat(81) },
      },
    });
    const result = parseFlowFile(text);
    expect(result.ok && result.connections).toEqual({ c1: { type: "github", name: "prod-gh" } });
  });

  it("gives no hints for a bare graph or a non-object field", () => {
    expect(parseFlowFile(JSON.stringify(g))).toMatchObject({ ok: true, connections: {} });
    const text = JSON.stringify({ ...buildFlowFile("x", g), connections: [1, 2] });
    expect(parseFlowFile(text)).toMatchObject({ ok: true, connections: {} });
  });
});

describe("planConnections", () => {
  const g = graph([request("a", "c1"), request("b", "c1"), request("c", "c2")]);
  const hints = { c1: { type: "github", name: "prod-gh" } };

  it("asks about every connection this workspace does not have, with how many nodes use it", () => {
    const needs = planConnections(g, hints, []);
    expect(needs).toEqual([
      { fileId: "c1", name: "prod-gh", type: "github", nodes: 2, suggestion: null },
      { fileId: "c2", name: "A connection", type: "", nodes: 1, suggestion: null },
    ]);
  });

  it("asks about nothing when the connections already exist here", () => {
    expect(planConnections(g, hints, [ref("c1", "x", "github"), ref("c2", "y", "slack")])).toEqual([]);
  });

  it("suggests the connection with the same type and name", () => {
    const here = [ref("m1", "other", "github"), ref("m2", "prod-gh", "github")];
    expect(planConnections(g, hints, here)[0].suggestion).toBe("m2");
  });

  it("suggests the only connection of that type when no name matches", () => {
    expect(planConnections(g, hints, [ref("m1", "mine", "github")])[0].suggestion).toBe("m1");
  });

  it("does not guess between several of the type, or across types", () => {
    const several = [ref("m1", "a", "github"), ref("m2", "b", "github")];
    expect(planConnections(g, hints, several)[0].suggestion).toBeNull();
    expect(planConnections(g, hints, [ref("m3", "prod-gh", "slack")])[0].suggestion).toBeNull();
  });

  it("suggests nothing for a connection the file gave no hint for", () => {
    expect(planConnections(g, {}, [ref("m1", "mine", "github")])[1].suggestion).toBeNull();
  });
});

describe("applyConnections", () => {
  const g = graph([request("a", "c1"), request("b", "c2"), request("c", "c3"), request("d", "")]);
  const here = [ref("c1", "same workspace", "github")];

  it("replaces a connection with the one chosen", () => {
    expect(idOf(applyConnections(g, { c2: "m1" }, here), 1)).toBe("m1");
  });

  it("keeps an id that exists here, and clears one that does not and was not chosen", () => {
    const result = applyConnections(g, {}, here);
    expect([0, 1, 2, 3].map((i) => idOf(result, i))).toEqual(["c1", "", "", ""]);
  });

  it("clears a connection the user skipped", () => {
    expect(idOf(applyConnections(g, { c2: "" }, here), 1)).toBe("");
  });

  it("treats a prompt node like a request node", () => {
    const mixed = graph([request("a", "c1"), prompt("p", "c2"), prompt("q", "c3")]);
    expect(usedConnectionIds(mixed)).toEqual(["c1", "c2", "c3"]);
    const needs = planConnections(mixed, { c2: { type: "openai_compatible", name: "Groq" } }, here);
    expect(needs.map((n) => [n.fileId, n.nodes])).toEqual([
      ["c2", 1],
      ["c3", 1],
    ]);
    const result = applyConnections(mixed, { c2: "m1" }, here);
    expect([0, 1, 2].map((i) => idOf(result, i))).toEqual(["c1", "m1", ""]);
  });

  it("does not change other nodes or the original graph", () => {
    const withSubflow = graph([request("a", "c9"), subflow("s", "x")]);
    const result = applyConnections(withSubflow, {}, []);
    expect(result.nodes[1]).toBe(withSubflow.nodes[1]);
    expect(idOf(withSubflow, 0)).toBe("c9");
  });
});
