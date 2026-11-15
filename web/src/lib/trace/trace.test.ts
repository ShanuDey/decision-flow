import { describe, expect, it } from "vitest";

import type { RunStep } from "@/lib/api/models";

import { pollDelay } from "./poll";
import { summaryOf, visibleInput } from "./summary";
import { barOf, buildTree, formatStepDuration, nodeIdOf, totalMs } from "./tree";

function step(over: Partial<RunStep> & { id: string }): RunStep {
  return {
    parent_id: null,
    kind: "node",
    node_id: over.id,
    node_type: "assign",
    name: over.id,
    status: "ok",
    error: null,
    start_offset_ms: 0,
    duration_ms: 1,
    input: null,
    output: null,
    ...over,
  };
}

describe("buildTree", () => {
  it("nests children under their parent and keeps order", () => {
    const tree = buildTree([
      step({ id: "agent", node_type: "agent" }),
      step({ id: "llm", kind: "llm", node_id: null, parent_id: "agent" }),
      step({ id: "end", node_type: "end" }),
    ]);
    expect(tree.map((n) => n.step.id)).toEqual(["agent", "end"]);
    expect(tree[0].children.map((n) => n.step.id)).toEqual(["llm"]);
  });

  it("treats a step with an unknown parent as a root", () => {
    expect(buildTree([step({ id: "a", parent_id: "gone" })]).map((n) => n.step.id)).toEqual(["a"]);
  });
});

describe("totals and bars", () => {
  const steps = [step({ id: "a", duration_ms: 2 }), step({ id: "b", start_offset_ms: 8, duration_ms: 2 })];

  it("totals to the latest end", () => {
    expect(totalMs(steps)).toBe(10);
  });

  it("positions bars as percentages of the run", () => {
    expect(barOf(steps[1], 10)).toEqual({ left: 80, width: 20 });
  });

  it("never draws a bar thinner than the minimum, and keeps it inside the track", () => {
    const quick = step({ id: "q", start_offset_ms: 1000, duration_ms: 0 });
    const bar = barOf(quick, 1000);
    expect(bar.width).toBe(1.5);
    expect(bar.left + bar.width).toBeLessThanOrEqual(100);
  });

  it("handles an empty run", () => {
    expect(barOf(steps[0], 0)).toEqual({ left: 0, width: 100 });
  });
});

describe("formatStepDuration", () => {
  it("reads naturally at every scale", () => {
    expect(formatStepDuration(0)).toBe("<1 ms");
    expect(formatStepDuration(42.4)).toBe("42 ms");
    expect(formatStepDuration(1270)).toBe("1.27 s");
  });
});

describe("nodeIdOf", () => {
  it("only node steps map to a canvas node", () => {
    expect(nodeIdOf(step({ id: "a" }))).toBe("a");
    expect(nodeIdOf(step({ id: "t", kind: "tool", node_id: null }))).toBeNull();
  });
});

describe("summaryOf", () => {
  it("shows a condition's result", () => {
    const s = step({ id: "c", node_type: "condition", output: { expression: "x", result: true } });
    expect(summaryOf(s)).toEqual({ text: "true", tone: "good" });
    expect(summaryOf({ ...s, output: { result: false } })).toEqual({ text: "false", tone: "neutral" });
  });

  it("summarises an assign by what it set", () => {
    expect(summaryOf(step({ id: "a", output: { decision: "approved" } }))).toEqual({
      text: "decision = approved",
      tone: "neutral",
    });
    expect(summaryOf(step({ id: "a", output: { a: 1, b: 2 } }))?.text).toBe("2 variables");
  });

  it("never prints undefined for a value JSON cannot show", () => {
    expect(summaryOf(step({ id: "a", output: { fn: () => 1 } }))?.text).not.toContain("undefined");
  });

  it("flags a failed step and gives unknown node types no chip", () => {
    expect(summaryOf(step({ id: "x", status: "failed" }))).toEqual({ text: "error", tone: "bad" });
    expect(summaryOf(step({ id: "h", node_type: "http", output: { status: 200 } }))).toBeNull();
  });
});

describe("visibleInput", () => {
  const input = { input: { a: 1 }, vars: {}, nodes: { start: { output: {} } } };
  const node = step({ id: "n", input });

  it("hides the repeated state of earlier nodes by default", () => {
    expect(visibleInput(node, false)).toEqual({ value: { input: { a: 1 }, vars: {} }, trimmed: true });
  });

  it("shows everything on request", () => {
    expect(visibleInput(node, true)).toEqual({ value: input, trimmed: false });
  });

  it("leaves non-node spans alone", () => {
    const tool = step({ id: "t", kind: "tool", node_id: null, input: { q: 1 } });
    expect(visibleInput(tool, false)).toEqual({ value: { q: 1 }, trimmed: false });
  });
});

describe("pollDelay", () => {
  it("backs off to a ceiling", () => {
    expect([0, 1, 2, 3, 4, 8].map(pollDelay)).toEqual([1000, 1500, 2250, 3375, 5000, 5000]);
  });

  it("checks about nine times in under half a minute", () => {
    const waits = Array.from({ length: 8 }, (_, poll) => pollDelay(poll));
    expect(waits.reduce((a, b) => a + b, 0)).toBeLessThan(30_000);
  });
});
