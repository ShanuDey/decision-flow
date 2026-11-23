import { describe, expect, it } from "vitest";

import { createNode, defaultData, NODE_SPECS } from "./nodes";
import { fieldNameProblem, STRUCTURED_TYPES } from "./structured-output";
import { outputKeys } from "./suggest";
import type { Graph } from "./types";

describe("fieldNameProblem", () => {
  it("accepts names a later node can read", () => {
    expect(fieldNameProblem(["city", "zip_code", "_x1"], 1)).toBeNull();
  });

  it("refuses empty, unreadable and repeated names", () => {
    expect(fieldNameProblem([" "], 0)).toMatch(/name/);
    expect(fieldNameProblem(["1a"], 0)).toMatch(/digit/);
    expect(fieldNameProblem(["a b"], 0)).toMatch(/letters/);
    expect(fieldNameProblem(["a", "a"], 1)).toMatch(/Another/);
    expect(fieldNameProblem(["a", "a"], 0)).toBeNull();
  });
});

describe("the structured output node type", () => {
  it("offers every type the API supports, and no object", () => {
    expect(STRUCTURED_TYPES.map((t) => t.value)).toEqual(["string", "number", "boolean", "enum", "array"]);
  });

  it("is a pickable data node with empty defaults", () => {
    expect(NODE_SPECS.structured_output).toMatchObject({ label: "Structured output", pickable: true });
    expect(defaultData("structured_output")).toMatchObject({ fields: [], mode: "schema", connection_id: "" });
    expect(createNode("structured_output", [], { x: 0, y: 0 })).toMatchObject({ id: "structured_output" });
  });

  it("offers each named field to later nodes", () => {
    const data = {
      ...defaultData("structured_output"),
      fields: [
        { name: "city", type: "string" as const },
        { name: "", type: "number" as const },
        { name: "score", type: "number" as const },
      ],
    };
    const node = { id: "ask", type: "structured_output", name: "Ask", position: { x: 0, y: 0 }, data } as const;
    const graph: Graph = { schema_version: 1, variables: [], nodes: [node], edges: [] };
    expect(outputKeys(node, graph)).toEqual([
      { name: "city", type: "string" },
      { name: "score", type: "number" },
    ]);
  });
});
