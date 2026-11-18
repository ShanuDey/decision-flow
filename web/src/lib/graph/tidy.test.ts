import { describe, expect, it } from "vitest";

import type { FlowEdge, FlowNode } from "./convert";
import { tidy } from "./tidy";

const node = (id: string, type: FlowNode["type"]): FlowNode => ({
  id,
  type,
  position: { x: 0, y: 0 },
  data: { name: id, config: {} as never },
});

const sizes = Object.fromEntries(
  ["start", "check", "yes", "no", "end", "lone"].map((id) => [id, { width: 200, height: 80 }]),
);

const nodes = [
  node("start", "start"),
  node("check", "condition"),
  node("yes", "assign"),
  node("no", "assign"),
  node("end", "end"),
  node("lone", "assign"),
];
const edges: FlowEdge[] = [
  { id: "e1", source: "start", target: "check" },
  { id: "e2", source: "check", target: "no", sourceHandle: "false" },
  { id: "e3", source: "check", target: "yes", sourceHandle: "true" },
  { id: "e4", source: "yes", target: "end" },
  { id: "e5", source: "no", target: "end" },
];

describe("tidy", () => {
  const out = tidy(nodes, edges, sizes);

  it("flows left to right", () => {
    expect(out.start.x).toBeLessThan(out.check.x);
    expect(out.check.x).toBeLessThan(out.yes.x);
    expect(out.yes.x).toBeLessThan(out.end.x);
  });

  it("puts the true branch above the false branch", () => {
    expect(out.yes.y).toBeLessThan(out.no.y);
  });

  it("places every node, including unconnected ones, without overlap", () => {
    expect(Object.keys(out).sort()).toEqual(nodes.map((n) => n.id).sort());
    const boxes = Object.values(out);
    for (const [i, a] of boxes.entries()) {
      for (const b of boxes.slice(i + 1)) {
        const apart = Math.abs(a.x - b.x) >= 200 || Math.abs(a.y - b.y) >= 80;
        expect(apart).toBe(true);
      }
    }
  });

  it("is deterministic", () => {
    expect(tidy(nodes, edges, sizes)).toEqual(out);
  });

  it("ignores edges to missing nodes", () => {
    const stray = [...edges, { id: "x", source: "start", target: "gone" }];
    expect(tidy(nodes, stray, sizes)).toEqual(out);
  });
});
