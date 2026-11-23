import { describe, expect, it } from "vitest";

import { parseIterations, parseMaxSeconds, toolNameProblem } from "./agent";
import { defaultData } from "./nodes";
import { calledFlowIds } from "./subflow";
import { parseFlowFile } from "./transfer";
import type { Graph } from "./types";

const FLOW_A = "0a6c2f7e-4b1d-4e0a-8c55-3d1e9f2a7b64";

function graphWith(tools: { flow_id: string; name: string; description: string }[]): Graph {
  return {
    schema_version: 1,
    variables: [],
    nodes: [
      {
        id: "bot",
        type: "agent",
        name: "Agent",
        position: { x: 0, y: 0 },
        data: { ...(defaultData("agent") as object), tools } as never,
      },
    ],
    edges: [],
  } as unknown as Graph;
}

describe("parseIterations", () => {
  it("needs a whole number from 1 to 50", () => {
    expect(parseIterations("8")).toEqual({ ok: true, value: 8 });
    for (const bad of ["", "0", "51", "2.5", "x"]) expect(parseIterations(bad).ok).toBe(false);
  });
});

describe("parseMaxSeconds", () => {
  it("allows empty and whole seconds", () => {
    expect(parseMaxSeconds("")).toEqual({ ok: true, value: null });
    expect(parseMaxSeconds("30")).toEqual({ ok: true, value: 30 });
    expect(parseMaxSeconds("0").ok).toBe(false);
  });
});

describe("toolNameProblem", () => {
  it("flags empty, invalid and repeated names", () => {
    expect(toolNameProblem(["a", "b"], 0)).toBeNull();
    expect(toolNameProblem(["", "b"], 0)).toMatch(/name/);
    expect(toolNameProblem(["bad name"], 0)).toMatch(/letters/);
    expect(toolNameProblem(["a", "a"], 1)).toMatch(/Another tool/);
  });
});

describe("agent tools", () => {
  it("count as called flows, once each", () => {
    const tool = { flow_id: FLOW_A, name: "a", description: "x" };
    const g = graphWith([tool, { ...tool, name: "b" }, { ...tool, flow_id: "" }]);
    expect(calledFlowIds(g)).toEqual([FLOW_A]);
  });

  it("lose their flow ids when a file is imported", () => {
    const g = graphWith([{ flow_id: FLOW_A, name: "a", description: "x" }]);
    const result = parseFlowFile(JSON.stringify(g));
    expect(result.ok && result.clearedSubflows).toBe(1);
    const node = result.ok ? result.graph.nodes[0] : null;
    expect(node?.type === "agent" && node.data.tools[0]).toEqual({ flow_id: "", name: "a", description: "x" });
  });
});
