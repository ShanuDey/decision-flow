import { ChevronLeft, CircleX } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { RetryButton } from "@/components/retry-button";
import { TraceView } from "@/components/trace/trace-view";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getRun } from "@/lib/api/client";
import { serverApiInit } from "@/lib/auth/session";
import { call, errorText, isUnreachable, UNREACHABLE_MESSAGE } from "@/lib/call";
import { formatDateTime, formatDuration } from "@/lib/format";

import { FlowCell } from "../flow-cell";
import { RunStatus } from "../run-status";

export const metadata: Metadata = { title: "Run · Decision Flow" };
export const maxDuration = 60;

function Json({ value }: { value: unknown }) {
  return (
    <pre className="max-h-96 overflow-auto rounded-lg bg-muted p-3 font-mono text-xs">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

export default async function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const init = await serverApiInit();
  const result = await call(getRun(id, init));

  if (!result.ok) {
    if (result.error.status === 404 || result.error.status === 422) notFound();
    return (
      <div className="mx-auto flex max-w-5xl flex-col gap-4">
        <p role="alert" className="flex items-center gap-2 rounded-xl border p-4 text-sm">
          <CircleX className="size-4 text-red-600 dark:text-red-400" aria-hidden />
          {isUnreachable(result.error)
            ? UNREACHABLE_MESSAGE
            : `Could not load the run: ${errorText(result.error)}`}
          <RetryButton />
        </p>
      </div>
    );
  }

  const run = result.data;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex flex-col gap-3">
        <Link href="/runs" className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:underline">
          <ChevronLeft className="size-4" aria-hidden /> All runs
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">Run</h1>
          <span className="font-mono text-sm text-muted-foreground">{run.run_id.slice(0, 8)}</span>
          <RunStatus run={run} />
          {run.test && <Badge variant="outline">Test</Badge>}
        </div>
        <dl className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
          <div className="flex gap-1.5">
            <dt>Flow</dt>
            <dd>
              <FlowCell run={run} />
            </dd>
          </div>
          <div className="flex gap-1.5">
            <dt>Started</dt>
            <dd className="font-medium text-foreground">{formatDateTime(run.started_at)}</dd>
          </div>
          <div className="flex gap-1.5">
            <dt>Duration</dt>
            <dd className="font-medium text-foreground">{formatDuration(run.duration_ms)}</dd>
          </div>
        </dl>
        {run.error && (
          <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            Failed in node <code>{run.error.node_id}</code>: {run.error.message}
          </p>
        )}
      </div>

      <Tabs defaultValue="trace">
        <TabsList>
          <TabsTrigger value="trace">Trace</TabsTrigger>
          <TabsTrigger value="input">Input</TabsTrigger>
          <TabsTrigger value="output">Output</TabsTrigger>
        </TabsList>
        <TabsContent value="trace" className="pt-2">
          <TraceView runId={run.run_id} />
        </TabsContent>
        <TabsContent value="input" className="pt-2">
          <Json value={run.input} />
        </TabsContent>
        <TabsContent value="output" className="pt-2">
          {run.output ? <Json value={run.output} /> : <p className="text-sm text-muted-foreground">No output.</p>}
        </TabsContent>
      </Tabs>
    </div>
  );
}
