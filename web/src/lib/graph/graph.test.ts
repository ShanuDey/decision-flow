import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { fromReactFlow, parseDraft, toReactFlow } from "./convert";
import { canAdd, canConnect, createNode, slug, uniqueId, uniqueName } from "./nodes";

const FLOWS = join(__dirname, "../../../../examples/flows");
const examples = readdirSync(FLOWS)
  .filter((f) => f.endsWith(".json"))
  .map((f) => [f, JSON.parse(readFileSync(join(FLOWS, f), "utf8"))] as const);

describe("convert", () => {
  it.each(examples)("round-trips %s", (_name, raw) => {
    const graph = parseDraft(raw);
    expect(graph).not.toBeNull();
    expect(fromReactFlow(toReactFlow(graph!))).toEqual(graph);
  });

  it("rejects drafts without the top-level shape", () => {
    expect(parseDraft({})).toBeNull();
    expect(parseDraft(null)).toBeNull();
    expect(parseDraft({ schema_version: 2, nodes: [], edges: [] })).toBeNull();
  });

  it("defaults missing variables to an empty list", () => {
    expect(parseDraft({ schema_version: 1, nodes: [], edges: [] })?.variables).toEqual([]);
  });
});

describe("ids and names", () => {
  it("slugs names into valid ids", () => {
    expect(slug("Check amount")).toBe("check_amount");
    expect(slug("  Assign -- values! ")).toBe("assign_values");
    expect(slug("1st step")).toBe("");
    expect(slug("日本語")).toBe("");
    expect(slug("x".repeat(60))).toHaveLength(40);
  });

  it("suffixes colliding names and ids", () => {
    expect(uniqueName("End", ["End"])).toBe("End 2");
    expect(uniqueName("End", ["End", "End 2"])).toBe("End 3");
    expect(uniqueId("End", "end", ["end"])).toBe("end_2");
  });

  it("avoids reserved words and falls back to the type plus a counter", () => {
    expect(uniqueId("Input", "assign", [])).toBe("input_2");
    expect(uniqueId("日本語", "assign", ["assign_1"])).toBe("assign_2");
  });

  it("keeps suffixed ids within the length limit", () => {
    const long = "a".repeat(40);
    const id = uniqueId(long, "assign", [long]);
    expect(id).toHaveLength(40);
    expect(id.endsWith("_2")).toBe(true);
  });
});

describe("node rules", () => {
  const start = { id: "start", name: "Start", type: "start" as const };

  it("allows exactly one Start and any number of End/Assign nodes", () => {
    expect(canAdd("start", [start])).toBe(false);
    expect(canAdd("start", [])).toBe(true);
    expect(canAdd("end", [])).toBe(true);
    expect(canAdd("assign", [start])).toBe(true);
  });

  it("forbids edges into Start and out of End", () => {
    expect(canConnect("start", "assign")).toBe(true);
    expect(canConnect("assign", "end")).toBe(true);
    expect(canConnect("assign", "start")).toBe(false);
    expect(canConnect("end", "assign")).toBe(false);
  });

  it("creates nodes with a unique name and an id derived from it", () => {
    const first = createNode("assign", [start], { x: 1, y: 2 });
    expect(first).toMatchObject({
      id: "assign_values",
      name: "Assign values",
      data: { assignments: [] },
    });
    const second = createNode("assign", [start, first], { x: 0, y: 0 });
    expect(second).toMatchObject({ id: "assign_values_2", name: "Assign values 2" });
  });
});
