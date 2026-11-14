import { NODE_SPECS, NODE_TYPES, type NodeGroup, type NodeSource } from "./nodes";
import type { NodeType } from "./types";

export type SourceFilter = "all" | NodeSource;

export interface PickerGroup {
  group: NodeGroup;
  types: NodeType[];
}

const GROUP_ORDER: NodeGroup[] = ["Flow", "Logic", "Data"];

export function pickerGroups(query: string, source: SourceFilter): PickerGroup[] {
  const needle = query.trim().toLowerCase();
  const matches = (type: NodeType) => {
    const spec = NODE_SPECS[type];
    if (source !== "all" && spec.source !== source) return false;
    return !needle || `${spec.label} ${spec.description} ${spec.group}`.toLowerCase().includes(needle);
  };
  return GROUP_ORDER.map((group) => ({
    group,
    types: NODE_TYPES.filter((t) => NODE_SPECS[t].group === group && matches(t)),
  })).filter((g) => g.types.length > 0);
}

export function flatTypes(groups: PickerGroup[]): NodeType[] {
  return groups.flatMap((g) => g.types);
}

export function ioSummary(type: NodeType): { inputs: string; outputs: string } {
  const spec = NODE_SPECS[type];
  const outputs = spec.handles.length
    ? spec.handles.join(", ")
    : spec.acceptsOutgoing
      ? "1"
      : "none";
  return { inputs: spec.acceptsIncoming ? "1" : "none", outputs };
}
