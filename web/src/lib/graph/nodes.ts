import type { NodeData, NodeDataByType, NodeType, Position } from "./types";

export interface NodeSpec {
  label: string;
  description: string;
  minCount: number;
  maxCount: number | null;
  acceptsIncoming: boolean;
  acceptsOutgoing: boolean;
  handles: readonly string[];
}

// Mirrors the ClassVars on the Python node models (min_count, max_count, accepts_*, handles).
export const NODE_SPECS: Record<NodeType, NodeSpec> = {
  start: {
    label: "Start",
    description: "Declares the flow's inputs",
    minCount: 1,
    maxCount: 1,
    acceptsIncoming: false,
    acceptsOutgoing: true,
    handles: [],
  },
  assign: {
    label: "Assign values",
    description: "Set flow variables",
    minCount: 0,
    maxCount: null,
    acceptsIncoming: true,
    acceptsOutgoing: true,
    handles: [],
  },
  condition: {
    label: "Condition",
    description: "Branch on a true/false expression",
    minCount: 0,
    maxCount: null,
    acceptsIncoming: true,
    acceptsOutgoing: true,
    handles: ["true", "false"],
  },
  end: {
    label: "End",
    description: "Maps state to the flow's output",
    minCount: 1,
    maxCount: null,
    acceptsIncoming: true,
    acceptsOutgoing: false,
    handles: [],
  },
};

export const NODE_TYPES = Object.keys(NODE_SPECS) as NodeType[];

const RESERVED_IDS = new Set(["input", "vars", "nodes", "secrets", "env", "run"]);
const MAX_ID_LENGTH = 40;

export interface NodeRef {
  id: string;
  name: string;
  type: NodeType;
}

export function slug(name: string): string {
  const base = name
    .normalize("NFKD")
    .replace(/[^\x00-\x7F]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return /^[a-z]/.test(base) ? base.slice(0, MAX_ID_LENGTH) : "";
}

function withSuffix(base: string, n: number, sep: string, max?: number): string {
  const suffix = `${sep}${n}`;
  return `${max ? base.slice(0, max - suffix.length) : base}${suffix}`;
}

export function uniqueName(base: string, taken: Iterable<string>): string {
  const used = new Set(taken);
  if (!used.has(base)) return base;
  for (let n = 2; ; n++) {
    const candidate = withSuffix(base, n, " ");
    if (!used.has(candidate)) return candidate;
  }
}

export function uniqueId(name: string, type: NodeType, taken: Iterable<string>): string {
  const used = new Set(taken);
  const base = slug(name);
  const free = (id: string) => !used.has(id) && !RESERVED_IDS.has(id);
  if (base && free(base)) return base;
  if (base) {
    for (let n = 2; ; n++) {
      const candidate = withSuffix(base, n, "_", MAX_ID_LENGTH);
      if (free(candidate)) return candidate;
    }
  }
  for (let n = 1; ; n++) {
    const candidate = `${type}_${n}`;
    if (free(candidate)) return candidate;
  }
}

export function canAdd(type: NodeType, existing: readonly NodeRef[]): boolean {
  const { maxCount } = NODE_SPECS[type];
  return maxCount === null || existing.filter((n) => n.type === type).length < maxCount;
}

export function canConnect(source: NodeType, target: NodeType): boolean {
  return NODE_SPECS[source].acceptsOutgoing && NODE_SPECS[target].acceptsIncoming;
}

export function defaultData<T extends NodeType>(type: T): NodeDataByType[T];
export function defaultData(type: NodeType): NodeData {
  switch (type) {
    case "start":
      return { inputs: [] };
    case "end":
      return { outputs: [] };
    case "assign":
      return { assignments: [] };
    case "condition":
      return { expression: "" };
  }
}

export interface NewNode {
  id: string;
  type: NodeType;
  name: string;
  position: Position;
  data: NodeData;
}

export function createNode(
  type: NodeType,
  existing: readonly NodeRef[],
  position: Position,
): NewNode {
  const name = uniqueName(
    NODE_SPECS[type].label,
    existing.map((n) => n.name),
  );
  const id = uniqueId(
    name,
    type,
    existing.map((n) => n.id),
  );
  return { id, type, name, position, data: defaultData(type) };
}
