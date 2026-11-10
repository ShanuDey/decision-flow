// Hand-written mirror of the graph JSON contract (api/app/engine/graph.py, nodes/*.py).
// The OpenAPI draft body is an untyped object because invalid drafts must stay saveable.

export type FieldType = "string" | "number" | "boolean" | "object" | "array" | "enum";

export const FIELD_TYPES: FieldType[] = ["string", "number", "boolean", "object", "array", "enum"];

export interface FieldDef {
  name: string;
  type: FieldType;
  values?: string[];
  required?: boolean;
  default?: unknown;
}

export interface Variable {
  name: string;
  type: FieldType;
  values?: string[];
  initial?: unknown;
}

export interface OutputDef {
  name: string;
  type: FieldType;
  values?: string[];
  value: string;
}

export interface Assignment {
  variable: string;
  value: string;
}

export interface StartData {
  inputs: FieldDef[];
}
export interface EndData {
  outputs: OutputDef[];
}
export interface AssignData {
  assignments: Assignment[];
}

export interface NodeDataByType {
  start: StartData;
  end: EndData;
  assign: AssignData;
}

export type NodeType = keyof NodeDataByType;
export type NodeData = NodeDataByType[NodeType];

export interface Position {
  x: number;
  y: number;
}

export type GraphNode = {
  [T in NodeType]: {
    id: string;
    type: T;
    name: string;
    position: Position;
    data: NodeDataByType[T];
  };
}[NodeType];

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle: string | null;
}

export interface Graph {
  schema_version: 1;
  variables: Variable[];
  nodes: GraphNode[];
  edges: GraphEdge[];
}
