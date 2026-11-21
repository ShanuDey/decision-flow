"use client";

import { Loader2 } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { errorText } from "@/lib/call";
import { buildTree, formatStepDuration, totalMs } from "@/lib/trace/tree";

import type { Format } from "./io-block";
import { Segmented } from "./segmented";
import { StepRows, type TraceContext, type ViewMode } from "./step-row";
import { type StepsFetcher, useRunSteps } from "./use-run-steps";

function toggled(set: ReadonlySet<string>, id: string): Set<string> {
  const next = new Set(set);
  if (!next.delete(id)) next.add(id);
  return next;
}

function Notice({ children, action }: { children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div role="status" className="flex flex-wrap items-center gap-3 rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
      {children}
      {action}
    </div>
  );
}

export function TraceView({
  runId,
  onSelectNode,
  fetchSteps,
}: {
  // The id of the trace's owner: a run, or an agent message when `fetchSteps` is given.
  runId: string;
  onSelectNode?: (nodeId: string) => void;
  fetchSteps?: StepsFetcher;
}) {
  const { state, reload } = useRunSteps(runId, fetchSteps);
  const [mode, setMode] = useState<ViewMode>("list");
  const [format, setFormat] = useState<Format>("pretty");
  const [open, setOpen] = useState<string | null>(null);
  const [folded, setFolded] = useState<ReadonlySet<string>>(new Set());
  const [full, setFull] = useState<ReadonlySet<string>>(new Set());

  const tree = useMemo(() => buildTree(state.kind === "ready" ? state.steps : []), [state]);
  const steps = state.kind === "ready" ? state.steps : [];

  if (state.kind === "loading") {
    return (
      <Notice>
        <Loader2 className="size-4 animate-spin" aria-hidden /> Loading steps…
      </Notice>
    );
  }
  if (state.kind === "pending") {
    return (
      <Notice>
        <Loader2 className="size-4 animate-spin" aria-hidden /> The trace is not ready yet. Checking again in a moment.
      </Notice>
    );
  }
  if (state.kind === "timeout") {
    return (
      <Notice action={<Button size="sm" variant="outline" onClick={reload}>Check again</Button>}>
        The trace is taking longer than usual to appear.
      </Notice>
    );
  }
  if (state.kind === "error") {
    return (
      <Notice action={<Button size="sm" variant="outline" onClick={reload}>Retry</Button>}>
        {state.error.status === 503
          ? "Step history is unavailable right now. The run itself completed."
          : `Could not load the steps: ${errorText(state.error)}`}
      </Notice>
    );
  }
  if (steps.length === 0) {
    return <Notice>No step history is available for this run.</Notice>;
  }

  const ctx: TraceContext = {
    total: totalMs(steps),
    mode,
    format,
    open,
    folded,
    full,
    toggleOpen: (id) => setOpen((cur) => (cur === id ? null : id)),
    toggleFold: (id) => setFolded((cur) => toggled(cur, id)),
    toggleFull: (id) => setFull((cur) => toggled(cur, id)),
    onSelectNode,
  };

  return (
    <div className="flex min-w-0 flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          {steps.length} {steps.length === 1 ? "step" : "steps"} · {formatStepDuration(ctx.total)} total
        </p>
        <div className="flex gap-2">
          <Segmented
            label="Format"
            value={format}
            onChange={setFormat}
            options={[
              { value: "pretty", label: "Pretty" },
              { value: "json", label: "JSON" },
            ]}
          />
          <Segmented
            label="View"
            value={mode}
            onChange={setMode}
            options={[
              { value: "list", label: "List" },
              { value: "timeline", label: "Timeline" },
            ]}
          />
        </div>
      </div>
      <div>
        <StepRows nodes={tree} ctx={ctx} />
      </div>
    </div>
  );
}
