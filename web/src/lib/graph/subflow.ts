import type { FieldDef, FieldType, Graph } from "./types";

export interface PublishedFlow {
  id: string;
  name: string;
  version: number;
}

export interface FlowContract {
  inputs: FieldDef[];
  outputs: { name: string; type: FieldType }[];
}

// Keyed by flow id; null means the flow could not be read (missing or not published).
export type Contracts = Record<string, FlowContract | null>;

// Start's inputs and End's outputs (every End declares the same ones).
export function contractOf(graph: Graph): FlowContract {
  const start = graph.nodes.find((n) => n.type === "start");
  const end = graph.nodes.find((n) => n.type === "end");
  return {
    inputs: start?.type === "start" ? start.data.inputs : [],
    outputs:
      end?.type === "end" ? end.data.outputs.map((o) => ({ name: o.name, type: o.type })) : [],
  };
}

export function calledFlowIds(graph: Graph): string[] {
  const ids = graph.nodes.flatMap((n) => (n.type === "subflow" && n.data.flow_id ? [n.data.flow_id] : []));
  return [...new Set(ids)];
}

export function missingInputs(contract: FlowContract, inputs: Record<string, string>): string[] {
  return contract.inputs
    .filter((f) => (f.required ?? true) && f.default == null && !inputs[f.name]?.trim())
    .map((f) => f.name);
}

export function syncInputs(contract: FlowContract, inputs: Record<string, string>): Record<string, string> {
  return Object.fromEntries(contract.inputs.map((f) => [f.name, inputs[f.name] ?? ""]));
}
