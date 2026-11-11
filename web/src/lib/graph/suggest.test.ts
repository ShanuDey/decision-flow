import { describe, expect, it } from "vitest";

import { suggest } from "./suggest";
import type { Graph } from "./types";

const graph: Graph = {
  schema_version: 1,
  variables: [
    { name: "total", type: "number" },
    { name: "label", type: "string" },
  ],
  nodes: [
    {
      id: "start",
      type: "start",
      name: "Start",
      position: { x: 0, y: 0 },
      data: {
        inputs: [
          { name: "income", type: "number", required: true },
          { name: "region", type: "string" },
        ],
      },
    },
    {
      id: "set_total",
      type: "assign",
      name: "Set total",
      position: { x: 0, y: 0 },
      data: { assignments: [{ variable: "total", value: "1" }] },
    },
    {
      id: "check",
      type: "condition",
      name: "Check",
      position: { x: 0, y: 0 },
      data: { expression: "" },
    },
    {
      id: "later",
      type: "assign",
      name: "Later",
      position: { x: 0, y: 0 },
      data: { assignments: [] },
    },
    { id: "end", type: "end", name: "End", position: { x: 0, y: 0 }, data: { outputs: [] } },
  ],
  edges: [
    { id: "e1", source: "start", target: "set_total", sourceHandle: null },
    { id: "e2", source: "set_total", target: "check", sourceHandle: null },
    { id: "e3", source: "check", target: "later", sourceHandle: "true" },
    { id: "e4", source: "check", target: "end", sourceHandle: "false" },
    { id: "e5", source: "later", target: "end", sourceHandle: null },
  ],
};

const at = (text: string, node = "check") => suggest(graph, node, text, text.length);
const inserts = (text: string, node?: string) => at(text, node).items.map((i) => i.insert);

describe("suggest", () => {
  it("offers the three scopes for an empty expression and a partial word", () => {
    expect(inserts("")).toEqual(["input.", "vars.", "nodes."]);
    expect(inserts("in")).toEqual(["input."]);
    expect(inserts("input.income > 1 && v")).toEqual(["vars."]);
  });

  it("lists start inputs with their type", () => {
    expect(at("input.").items).toEqual([
      { insert: "input.income", label: "income", detail: "number · required" },
      { insert: "input.region", label: "region", detail: "string" },
    ]);
    expect(inserts("input.re")).toEqual(["input.region"]);
  });

  it("lists variables with their type", () => {
    expect(at("vars.").items.map((i) => [i.label, i.detail])).toEqual([
      ["total", "number"],
      ["label", "string"],
    ]);
  });

  it("lists only nodes that run before this one, by id", () => {
    expect(inserts("nodes.")).toEqual(["nodes.start.output.", "nodes.set_total.output."]);
    expect(inserts("nodes.", "end")).toContain("nodes.later.output.");
    expect(at("nodes.").items[1].detail).toBe("Set total · assign");
  });

  it("walks down to the output keys of each node type", () => {
    expect(inserts("nodes.start")).toEqual(["nodes.start.output."]);
    expect(inserts("nodes.start.")).toEqual(["nodes.start.output"]);
    expect(inserts("nodes.start.output.")).toEqual([
      "nodes.start.output.income",
      "nodes.start.output.region",
    ]);
    expect(at("nodes.set_total.output.").items[0]).toMatchObject({
      label: "total",
      detail: "number",
    });
    expect(inserts("nodes.check.output.", "end")).toEqual([
      "nodes.check.output.result",
      "nodes.check.output.expression",
    ]);
  });

  it("offers nothing for a node that does not run earlier", () => {
    expect(inserts("nodes.later.output.")).toEqual([]);
    expect(inserts("nodes.ghost.output.")).toEqual([]);
  });

  it("replaces just the path under the cursor", () => {
    const text = "input.in > 1 && vars.total";
    const { from, items } = suggest(graph, "check", text, 8);
    expect(from).toBe(0);
    expect(items.map((i) => i.insert)).toEqual(["input.income"]);
  });

  it("stays quiet inside string literals but works after them", () => {
    expect(inserts('input.region == "input.')).toEqual([]);
    expect(inserts(String.raw`input.region == 'a\'input.`)).toEqual([]);
    expect(inserts('input.region == "x" && input.')).toContain("input.income");
  });

  it("stays quiet after dots and non-identifier starts", () => {
    expect(inserts("1.")).toEqual([]);
    expect(inserts("a.input.")).toEqual([]);
  });
});
