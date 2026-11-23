import { describe, expect, it } from "vitest";

import type { ConnectionOption } from "@/lib/connections";

import { createNode, defaultData, NODE_SPECS } from "./nodes";
import { lacksBaseUrl, parseMaxTokens, parseTemperature, promptConnections } from "./prompt";
import { outputKeys } from "./suggest";
import type { Graph } from "./types";

const conn = (id: string, typeId: string): ConnectionOption => ({
  id,
  name: id,
  typeId,
  typeName: typeId,
  hosts: "",
});

describe("parseTemperature", () => {
  it("allows empty and 0 to 2", () => {
    expect(parseTemperature("")).toEqual({ ok: true, value: null });
    expect(parseTemperature(" 0 ")).toEqual({ ok: true, value: 0 });
    expect(parseTemperature("1.5")).toEqual({ ok: true, value: 1.5 });
    expect(parseTemperature("2")).toEqual({ ok: true, value: 2 });
  });

  it("refuses anything else", () => {
    for (const bad of ["-0.1", "2.1", "abc", "1,5"]) expect(parseTemperature(bad).ok).toBe(false);
  });
});

describe("parseMaxTokens", () => {
  it("allows empty and whole numbers from 1", () => {
    expect(parseMaxTokens("")).toEqual({ ok: true, value: null });
    expect(parseMaxTokens("256")).toEqual({ ok: true, value: 256 });
  });

  it("refuses zero, fractions and text", () => {
    for (const bad of ["0", "1.5", "-3", "many"]) expect(parseMaxTokens(bad).ok).toBe(false);
  });
});

describe("promptConnections", () => {
  const all = [conn("a", "openai_compatible"), conn("b", "bearer"), conn("c", "groq")];

  it("offers OpenAI-compatible connections", () => {
    expect(promptConnections(all, "").map((c) => c.id)).toEqual(["a"]);
  });

  it("keeps an already chosen connection of another type", () => {
    expect(promptConnections(all, "b").map((c) => c.id)).toEqual(["a", "b"]);
  });

  it("flags a chosen connection that has no base URL", () => {
    expect(lacksBaseUrl(all[1])).toBe(true);
    expect(lacksBaseUrl(all[0])).toBe(false);
    expect(lacksBaseUrl(undefined)).toBe(false);
  });
});

describe("the prompt node type", () => {
  it("is a pickable data node with empty defaults", () => {
    expect(NODE_SPECS.prompt).toMatchObject({ label: "Prompt", pickable: true, maxCount: null });
    expect(defaultData("prompt")).toEqual({
      connection_id: "",
      model: "",
      system: "",
      prompt: "",
      temperature: null,
      max_tokens: null,
      timeout_seconds: null,
    });
    expect(createNode("prompt", [], { x: 0, y: 0 })).toMatchObject({ id: "prompt", name: "Prompt" });
  });

  it("offers the reply fields to later nodes", () => {
    const node = { id: "ask", type: "prompt", name: "Ask", position: { x: 0, y: 0 }, data: defaultData("prompt") } as const;
    const graph: Graph = { schema_version: 1, variables: [], nodes: [node], edges: [] };
    expect(outputKeys(node, graph).map((k) => k.name)).toEqual(["text", "model", "finish_reason", "usage"]);
  });
});
