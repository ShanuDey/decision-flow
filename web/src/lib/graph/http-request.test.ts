import { describe, expect, it } from "vitest";

import { createNode, defaultData, NODE_SPECS } from "./nodes";
import { flatTypes, pickerGroups } from "./picker";
import { outputKeys } from "./suggest";
import type { Graph } from "./types";

describe("the HTTP Request node in the editor", () => {
  it("is offered in the picker under Data", () => {
    expect(NODE_SPECS.http_request.pickable).toBe(true);
    const data = pickerGroups("", "all").find((g) => g.group === "Data");
    expect(data?.types).toEqual(["assign", "http_request", "prompt", "subflow"]);
    expect(flatTypes(pickerGroups("http", "all"))).toEqual(["http_request"]);
    expect(flatTypes(pickerGroups("", "all"))).toEqual([
      "start",
      "end",
      "condition",
      "assign",
      "http_request",
      "prompt",
      "subflow",
    ]);
  });

  it("starts as an empty GET with no body", () => {
    expect(defaultData("http_request")).toEqual({
      method: "GET",
      url: "",
      headers: {},
      query: {},
      body_type: "none",
      body: null,
      timeout_seconds: null,
      fail_on_error_status: false,
      connection_id: "",
    });
    const node = createNode("http_request", [], { x: 0, y: 0 });
    expect(node.id).toBe("http_request");
    expect(node.name).toBe("HTTP Request");
  });

  it("offers its response fields to later nodes", () => {
    const node = { id: "call", type: "http_request", name: "Call", position: { x: 0, y: 0 }, data: defaultData("http_request") } as const;
    const graph = { schema_version: 1, variables: [], nodes: [node], edges: [] } as unknown as Graph;
    expect(outputKeys(node, graph).map((k) => k.name)).toEqual([
      "status",
      "ok",
      "headers",
      "body",
      "duration_ms",
    ]);
  });
});
