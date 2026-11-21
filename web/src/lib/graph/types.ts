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

export interface ConditionData {
  expression: string;
}

export interface HttpRequestData {
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  url: string;
  headers: Record<string, string>;
  query: Record<string, string>;
  body_type: "none" | "json" | "form" | "text";
  body: unknown;
  timeout_seconds: number | null;
  fail_on_error_status: boolean;
  connection_id: string;
}

export interface SubflowData {
  flow_id: string;
  inputs: Record<string, string>;
}

export interface PromptData {
  connection_id: string;
  // Empty: the connection's default model.
  model: string;
  system: string;
  prompt: string;
  temperature: number | null;
  max_tokens: number | null;
  timeout_seconds: number | null;
}

export interface OutputFieldDef {
  name: string;
  type: FieldType;
  values?: string[];
  description?: string;
}

export interface StructuredOutputData {
  connection_id: string;
  // Empty: the connection's default model.
  model: string;
  system: string;
  prompt: string;
  fields: OutputFieldDef[];
  // "schema": the provider enforces the structure. "json": it is only asked for a JSON object.
  mode: "schema" | "json";
  temperature: number | null;
  max_tokens: number | null;
  timeout_seconds: number | null;
}

export interface NodeDataByType {
  start: StartData;
  end: EndData;
  assign: AssignData;
  condition: ConditionData;
  http_request: HttpRequestData;
  prompt: PromptData;
  structured_output: StructuredOutputData;
  subflow: SubflowData;
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
