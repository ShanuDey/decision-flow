"use client";

import {
  Braces,
  Box,
  ChevronDown,
  ChevronRight,
  Circle,
  Flag,
  GitBranch,
  type LucideIcon,
  Play,
  Sparkles,
  Variable,
  Wrench,
} from "lucide-react";

import type { RunStep } from "@/lib/api/models";
import { type Chip, summaryOf, visibleInput } from "@/lib/trace/summary";
import { barOf, formatStepDuration, nodeIdOf, type StepNode } from "@/lib/trace/tree";
import { cn } from "@/lib/utils";

import { type Format, IoBlock } from "./io-block";

export type ViewMode = "list" | "timeline";

export interface TraceContext {
  total: number;
  mode: ViewMode;
  format: Format;
  open: string | null;
  folded: ReadonlySet<string>;
  full: ReadonlySet<string>;
  toggleOpen: (id: string) => void;
  toggleFold: (id: string) => void;
  toggleFull: (id: string) => void;
  onSelectNode?: (nodeId: string) => void;
  // Detail shows in its own pane (see `StepDetail`), not under the row.
  split?: boolean;
}

const NODE_ICONS: Record<string, LucideIcon> = {
  start: Play,
  assign: Variable,
  condition: GitBranch,
  end: Flag,
};
const KIND_ICONS: Record<string, LucideIcon> = { llm: Sparkles, tool: Wrench, parser: Braces, other: Circle };
const KIND_TONE: Record<string, string> = {
  llm: "bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300",
  tool: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  parser: "bg-cyan-100 text-cyan-700 dark:bg-cyan-950 dark:text-cyan-300",
};
const BAR_TONE: Record<string, string> = {
  llm: "bg-violet-400 dark:bg-violet-700",
  tool: "bg-amber-400 dark:bg-amber-700",
  parser: "bg-cyan-400 dark:bg-cyan-700",
};
const CHIP_TONE: Record<Chip["tone"], string> = {
  good: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  bad: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
  neutral: "bg-muted text-muted-foreground",
};

function StepIcon({ step }: { step: RunStep }) {
  const Icon =
    step.kind === "node" ? (step.node_type && NODE_ICONS[step.node_type]) || Box : KIND_ICONS[step.kind] || Circle;
  return (
    <span
      aria-hidden
      className={cn("grid size-5 shrink-0 place-items-center rounded", KIND_TONE[step.kind] ?? "border bg-muted text-muted-foreground")}
    >
      <Icon className="size-3" />
    </span>
  );
}

function Detail({ step, ctx, inline = true }: { step: RunStep; ctx: TraceContext; inline?: boolean }) {
  const input = visibleInput(step, ctx.full.has(step.id));
  return (
    <div className={cn("grid gap-3", inline && "mt-1 mb-2 ml-9 rounded-lg border bg-background p-3 sm:grid-cols-2")}>
      <IoBlock
        title="Input"
        value={input.value}
        format={ctx.format}
        footer={
          (input.trimmed || ctx.full.has(step.id)) && (
            <button
              type="button"
              onClick={() => ctx.toggleFull(step.id)}
              className="mt-1 text-xs text-primary hover:underline"
            >
              {ctx.full.has(step.id) ? "Hide full state" : "Show full state"}
            </button>
          )
        }
      />
      <IoBlock title="Output" value={step.output} format={ctx.format} />
      {step.error && (
        <p role="alert" className="rounded-md bg-red-50 p-2 text-xs text-red-700 sm:col-span-2 dark:bg-red-950 dark:text-red-300">
          {step.error}
        </p>
      )}
    </div>
  );
}

export function StepDetail({ step, ctx }: { step: RunStep; ctx: TraceContext }) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <StepIcon step={step} />
        <h3 className="text-base font-semibold">{step.name}</h3>
        {step.node_type && <span className="text-xs text-muted-foreground">{step.node_type}</span>}
        <span className="text-xs text-muted-foreground tabular-nums">{formatStepDuration(step.duration_ms)}</span>
      </div>
      <Detail step={step} ctx={ctx} inline={false} />
    </div>
  );
}

// `nested` marks steps of a called flow: their node ids belong to that flow, not this canvas.
export function StepRows({ nodes, ctx, nested = false }: { nodes: StepNode[]; ctx: TraceContext; nested?: boolean }) {
  return (
    <>
      {nodes.map(({ step, children }) => {
        const open = ctx.open === step.id;
        const folded = ctx.folded.has(step.id);
        const chip = summaryOf(step);
        const bar = barOf(step, ctx.total);
        const timeline = ctx.mode === "timeline";
        return (
          <div key={step.id}>
            <div
              className={cn(
                "grid items-center gap-2 rounded-lg px-1 hover:bg-muted",
                timeline ? "grid-cols-[minmax(9rem,2fr)_minmax(5rem,3fr)_4.5rem]" : "grid-cols-[minmax(0,1fr)_4.5rem]",
                open && "bg-muted",
              )}
            >
              <div className="flex min-w-0 items-center">
                {children.length > 0 ? (
                  <button
                    type="button"
                    aria-label={folded ? "Expand children" : "Collapse children"}
                    onClick={() => ctx.toggleFold(step.id)}
                    className="grid size-6 place-items-center text-muted-foreground"
                  >
                    {folded ? <ChevronRight className="size-3.5" /> : <ChevronDown className="size-3.5" />}
                  </button>
                ) : (
                  <span className="size-6" />
                )}
                <button
                  type="button"
                  aria-expanded={open}
                  onClick={() => {
                    const opening = !open;
                    ctx.toggleOpen(step.id);
                    const nodeId = nodeIdOf(step);
                    if (opening && nodeId && !nested) ctx.onSelectNode?.(nodeId);
                  }}
                  className="flex min-w-0 flex-1 items-center gap-2 py-1.5 text-left text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
                >
                  <StepIcon step={step} />
                  <span className="truncate">{step.name}</span>
                  {step.node_type && <span className="shrink-0 text-xs text-muted-foreground">{step.node_type}</span>}
                  {chip && (
                    <span className={cn("max-w-48 shrink-0 truncate rounded-full px-2 text-xs", CHIP_TONE[chip.tone])}>
                      {chip.text}
                    </span>
                  )}
                </button>
              </div>
              {timeline && (
                <div aria-hidden className="relative h-2 rounded bg-muted-foreground/15">
                  <span
                    className={cn(
                      "absolute inset-y-0 rounded",
                      step.status === "failed" ? "bg-red-400 dark:bg-red-700" : (BAR_TONE[step.kind] ?? "bg-emerald-400 dark:bg-emerald-700"),
                    )}
                    style={{ left: `${bar.left}%`, width: `${bar.width}%` }}
                  />
                </div>
              )}
              <span className="text-right text-xs text-muted-foreground tabular-nums">
                {formatStepDuration(step.duration_ms)}
              </span>
            </div>
            {open && !ctx.split && <Detail step={step} ctx={ctx} />}
            {children.length > 0 && !folded && (
              <div className="ml-3 border-l pl-2">
                <StepRows nodes={children} ctx={ctx} nested={nested || step.node_type === "subflow"} />
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}
