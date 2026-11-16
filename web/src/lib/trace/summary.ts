import type { RunStep } from "@/lib/api/models";

export interface Chip {
  text: string;
  tone: "good" | "bad" | "neutral";
}

const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);

const SUMMARIES: Record<string, (step: RunStep) => Chip | null> = {
  condition: (step) => {
    const result = isRecord(step.output) ? step.output.result : undefined;
    return typeof result === "boolean" ? { text: String(result), tone: result ? "good" : "neutral" } : null;
  },
  http_request: (step) => {
    const status = isRecord(step.output) ? step.output.status : undefined;
    if (typeof status !== "number") return null;
    return { text: String(status), tone: status >= 200 && status < 300 ? "good" : "bad" };
  },
  assign: (step) => {
    if (!isRecord(step.output)) return null;
    const entries = Object.entries(step.output);
    if (entries.length === 0) return null;
    if (entries.length > 1) return { text: `${entries.length} variables`, tone: "neutral" };
    const [key, value] = entries[0];
    const shown = typeof value === "string" ? value : (JSON.stringify(value) ?? String(value));
    return { text: `${key} = ${shown}`, tone: "neutral" };
  },
};

export function summaryOf(step: RunStep): Chip | null {
  if (step.status === "failed") return { text: "error", tone: "bad" };
  return (step.node_type && SUMMARIES[step.node_type]?.(step)) || null;
}

export interface VisibleInput {
  value: unknown;
  // True when the full recorded state was cut down to the node's own input and variables.
  trimmed: boolean;
}

// A node span records the whole run state; by default show only what the node itself read.
export function visibleInput(step: RunStep, full: boolean): VisibleInput {
  const input = step.input;
  if (full || step.kind !== "node" || !isRecord(input) || !("nodes" in input)) {
    return { value: input, trimmed: false };
  }
  const rest = Object.fromEntries(Object.entries(input).filter(([key]) => key !== "nodes"));
  return { value: rest, trimmed: true };
}
