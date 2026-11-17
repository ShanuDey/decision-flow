import { describe, expect, it } from "vitest";

import { availableData } from "./scope";
import { calledFlowIds, contractOf, missingInputs, syncInputs } from "./subflow";
import { outputKeys, suggest } from "./suggest";
import type { Graph } from "./types";

const child: Graph = {
  schema_version: 1,
  variables: [],
  nodes: [
    {
      id: "start",
      type: "start",
      name: "Start",
      position: { x: 0, y: 0 },
      data: {
        inputs: [
          { name: "amount", type: "number", required: true },
          { name: "note", type: "string", required: false },
          { name: "tier", type: "string", required: true, default: "silver" },
        ],
      },
    },
    {
      id: "end",
      type: "end",
      name: "End",
      position: { x: 0, y: 0 },
      data: { outputs: [{ name: "total", type: "number", value: "{{ input.amount }}" }] },
    },
  ],
  edges: [],
};

function parent(flowId: string): Graph {
  return {
    schema_version: 1,
    variables: [],
    nodes: [
      { id: "start", type: "start", name: "Start", position: { x: 0, y: 0 }, data: { inputs: [] } },
      { id: "sub", type: "subflow", name: "Subflow", position: { x: 0, y: 0 }, data: { flow_id: flowId, inputs: {} } },
      { id: "end", type: "end", name: "End", position: { x: 0, y: 0 }, data: { outputs: [] } },
    ],
    edges: [
      { id: "e1", source: "start", target: "sub", sourceHandle: null },
      { id: "e2", source: "sub", target: "end", sourceHandle: null },
    ],
  };
}

describe("contractOf", () => {
  it("reads the inputs of Start and the outputs of End", () => {
    const contract = contractOf(child);
    expect(contract.inputs.map((i) => i.name)).toEqual(["amount", "note", "tier"]);
    expect(contract.outputs).toEqual([{ name: "total", type: "number" }]);
  });
});

describe("missingInputs", () => {
  it("lists required inputs with no value and no default", () => {
    const contract = contractOf(child);
    expect(missingInputs(contract, {})).toEqual(["amount"]);
    expect(missingInputs(contract, { amount: "{{ input.x }}" })).toEqual([]);
    expect(missingInputs(contract, { amount: "  " })).toEqual(["amount"]);
  });
});

describe("syncInputs", () => {
  it("has one row per input and keeps values that still apply", () => {
    const contract = contractOf(child);
    expect(syncInputs(contract, { amount: "1", gone: "2" })).toEqual({ amount: "1", note: "", tier: "" });
  });
});

describe("calledFlowIds", () => {
  it("lists each called flow once, skipping unpicked nodes", () => {
    expect(calledFlowIds(parent("a"))).toEqual(["a"]);
    expect(calledFlowIds(parent(""))).toEqual([]);
  });
});

describe("subflow outputs", () => {
  const contracts = { a: contractOf(child), gone: null };
  const graph = parent("a");
  const sub = graph.nodes[1];

  it("come from the called flow's End", () => {
    expect(outputKeys(sub, graph, contracts)).toEqual([{ name: "total", type: "number" }]);
    const gone = parent("gone");
    expect(outputKeys(gone.nodes[1], gone, contracts)).toEqual([]);
    expect(outputKeys(sub, graph)).toEqual([]);
  });

  it("are offered to later nodes", () => {
    const text = "nodes.sub.output.";
    const { items } = suggest(graph, "end", text, text.length, undefined, contracts);
    expect(items.map((i) => i.insert)).toEqual(["nodes.sub.output.total"]);
    const paths = availableData(graph, "end", undefined, contracts).flatMap((s) => s.items.map((i) => i.path));
    expect(paths).toContain("nodes.sub.output.total");
  });
});
