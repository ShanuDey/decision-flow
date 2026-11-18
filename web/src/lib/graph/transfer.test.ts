import { describe, expect, it } from "vitest";

import type { Graph } from "./types";
import { buildFlowFile, flowFileName, MAX_IMPORT_BYTES, parseFlowFile } from "./transfer";

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
    expect(result).toEqual({ ok: true, name: "My flow", graph: g, clearedSubflows: 0 });
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
