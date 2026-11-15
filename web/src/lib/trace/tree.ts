import type { RunStep } from "@/lib/api/models";

export interface StepNode {
  step: RunStep;
  children: StepNode[];
}

// Steps arrive ordered by start time; a step whose parent is unknown becomes a root.
export function buildTree(steps: RunStep[]): StepNode[] {
  const byId = new Map<string, StepNode>(steps.map((step) => [step.id, { step, children: [] }]));
  const roots: StepNode[] = [];
  for (const step of steps) {
    const node = byId.get(step.id)!;
    const parent = step.parent_id ? byId.get(step.parent_id) : undefined;
    (parent ? parent.children : roots).push(node);
  }
  return roots;
}

export function totalMs(steps: RunStep[]): number {
  return steps.reduce((max, s) => Math.max(max, s.start_offset_ms + s.duration_ms), 0);
}

export function nodeIdOf(step: RunStep): string | null {
  return step.kind === "node" ? step.node_id : null;
}

// A bar is never thinner than MIN_BAR, so sub-millisecond steps stay visible.
const MIN_BAR = 1.5;

export function barOf(step: RunStep, total: number): { left: number; width: number } {
  if (total <= 0) return { left: 0, width: 100 };
  const width = Math.max((step.duration_ms / total) * 100, MIN_BAR);
  const left = Math.min((step.start_offset_ms / total) * 100, 100 - width);
  return { left, width };
}

export function formatStepDuration(ms: number): string {
  if (ms < 1) return "<1 ms";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}
