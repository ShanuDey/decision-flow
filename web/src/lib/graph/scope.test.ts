import { describe, expect, it } from "vitest";

import { availableData, sampleScope } from "./scope";
import type { Graph } from "./types";

const graph: Graph = {
  schema_version: 1,
  variables: [{ name: "total", type: "number" }],
  nodes: [
    { id: "start", type: "start", name: "Start", position: { x: 0, y: 0 }, data: { inputs: [{ name: "score", type: "number", required: true }] } },
    { id: "cond", type: "condition", name: "Check", position: { x: 1, y: 0 }, data: { expression: "" } },
    { id: "end", type: "end", name: "End", position: { x: 2, y: 0 }, data: { outputs: [] } },
  ],
  edges: [
    { id: "e1", source: "start", target: "cond", sourceHandle: null },
    { id: "e2", source: "cond", target: "end", sourceHandle: "true" },
  ],
};

describe("availableData", () => {
  it("offers inputs, variables and only earlier nodes' outputs", () => {
    const forEnd = availableData(graph, "end");
    expect(forEnd.map((s) => s.title)).toEqual(["input", "vars", "nodes"]);
    expect(forEnd[0].items[0]).toEqual({ label: "score", path: "input.score", detail: "number" });
    expect(forEnd[2].items.map((i) => i.path)).toContain("nodes.cond.output.result");
    const forCond = availableData(graph, "cond");
    expect(forCond.find((s) => s.title === "nodes")?.items.map((i) => i.path)).toEqual([
      "nodes.start.output.score",
    ]);
  });
});

describe("sampleScope", () => {
  it("builds typed sample input, variables and earlier nodes' outputs", () => {
    const parsed = JSON.parse(sampleScope(availableData(graph, "end")));
    expect(parsed).toEqual({
      input: { score: 0 },
      vars: { total: 0 },
      nodes: {
        start: { output: { score: 0 } },
        cond: { output: { result: false, expression: "" } },
      },
    });
  });
});
