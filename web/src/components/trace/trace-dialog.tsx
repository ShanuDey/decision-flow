"use client";

import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";

import { TraceView } from "./trace-view";
import type { StepsFetcher } from "./use-run-steps";

// A trace in a large dialog: steps on the left, the chosen step's full input and output beside them.
export function TraceDialog({
  open,
  onOpenChange,
  title,
  runId,
  fetchSteps,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  runId: string;
  fetchSteps?: StepsFetcher;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[min(52rem,90dvh)] w-[min(90rem,94vw)] max-w-none flex-col gap-3 p-5 sm:max-w-none">
        <div className="pr-8">
          <DialogTitle>Trace</DialogTitle>
          <DialogDescription className="truncate">{title}</DialogDescription>
        </div>
        <TraceView key={runId} runId={runId} fetchSteps={fetchSteps} layout="split" />
      </DialogContent>
    </Dialog>
  );
}
