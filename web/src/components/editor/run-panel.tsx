"use client";

import { CircleCheck, CircleX, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { TraceView } from "@/components/trace/trace-view";
import { errorText } from "@/lib/call";

import type { RunOutcome } from "./actions";
import { useEditor } from "./store";

function Json({ value }: { value: unknown }) {
  return (
    <pre className="max-h-40 overflow-auto rounded-lg bg-muted p-3 font-mono text-xs">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

function Status({ outcome }: { outcome: RunOutcome }) {
  if (outcome.kind === "rejected") {
    return (
      <p role="status" className="flex items-center gap-2 text-sm">
        <CircleX className="size-4 text-red-600 dark:text-red-400" aria-hidden />
        Not run: {errorText(outcome.error)}
      </p>
    );
  }
  const { run } = outcome;
  const ok = run.status === "succeeded";
  return (
    <p role="status" className="flex flex-wrap items-center gap-2 text-sm">
      {ok ? (
        <CircleCheck className="size-4 text-emerald-600 dark:text-emerald-400" aria-hidden />
      ) : (
        <CircleX className="size-4 text-red-600 dark:text-red-400" aria-hidden />
      )}
      <span className="font-medium">{ok ? "Succeeded" : "Failed"}</span>
      <span className="text-muted-foreground">{run.duration_ms} ms</span>
      {run.error && (
        <span>
          in node <code>{run.error.node_id}</code>: {run.error.message}
        </span>
      )}
    </p>
  );
}

export function RunPanel({ outcome, onClose }: { outcome: RunOutcome; onClose: () => void }) {
  const output = outcome.kind === "finished" ? outcome.run.output : null;
  return (
    <section
      aria-label="Test run result"
      className="flex max-h-[45vh] shrink-0 flex-col gap-3 overflow-y-auto border-t bg-background p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <Status outcome={outcome} />
        <Button type="button" variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close result">
          <X aria-hidden />
        </Button>
      </div>
      <Tabs defaultValue="output">
        <TabsList>
          <TabsTrigger value="output">Output</TabsTrigger>
          <TabsTrigger value="input">Input</TabsTrigger>
          {outcome.kind === "finished" && <TabsTrigger value="trace">Trace</TabsTrigger>}
        </TabsList>
        <TabsContent value="output">
          {output ? (
            <Json value={output} />
          ) : (
            <p className="text-sm text-muted-foreground">No output.</p>
          )}
        </TabsContent>
        <TabsContent value="input">
          <Json value={outcome.input} />
        </TabsContent>
        {outcome.kind === "finished" && (
          <TabsContent value="trace" keepMounted>
            <TraceView
              key={outcome.run.run_id}
              runId={outcome.run.run_id}
              onSelectNode={(id) => useEditor.getState().selectOnly(id)}
            />
          </TabsContent>
        )}
      </Tabs>
    </section>
  );
}
