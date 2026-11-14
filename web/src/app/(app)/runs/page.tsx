import { ChevronLeft, ChevronRight, CircleX } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { RetryButton } from "@/components/retry-button";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { listFlows, listRuns } from "@/lib/api/client";
import type { ListFlowsSort } from "@/lib/api/models";
import { serverApiInit } from "@/lib/auth/session";
import { call, errorText, isUnreachable, UNREACHABLE_MESSAGE } from "@/lib/call";
import { formatDateTime, formatDuration } from "@/lib/format";
import { cn } from "@/lib/utils";

import {
  newerHref,
  olderHref,
  PAGE_SIZE,
  parseRunsQuery,
  testParam,
  type RunsQuery,
} from "./params";
import { RunStatus } from "./run-status";

export const metadata: Metadata = { title: "Runs · Decision Flow" };
export const maxDuration = 60;

const SELECT =
  "h-10 rounded-lg border border-input bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50";

export default async function RunsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const query = parseRunsQuery(await searchParams);
  const init = await serverApiInit();

  const [runs, flows] = await Promise.all([
    call(
      listRuns(
        {
          flow_id: query.flow,
          status: query.status,
          test: testParam(query.type),
          cursor: query.cursor,
          limit: PAGE_SIZE,
        },
        init,
      ),
    ),
    call(listFlows({ sort: "name" as ListFlowsSort, page: 1, page_size: 100 }, init)),
  ]);

  const flowOptions = flows.ok ? flows.data.items : [];
  const flowNames = new Map(flowOptions.map((f) => [f.id, f.name]));
  const filtered = Boolean(query.flow || query.status || query.type);
  const knownFlow = !query.flow || flowNames.has(query.flow);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Runs</h1>
        <p className="text-sm text-muted-foreground">Every execution, newest first.</p>
      </div>

      <form action="/runs" className="flex flex-wrap items-center gap-2" role="search">
        <label htmlFor="flow" className="sr-only">
          Flow
        </label>
        <select id="flow" name="flow" defaultValue={query.flow ?? ""} className={cn(SELECT, "max-w-56")}>
          <option value="">Flow: All</option>
          {!knownFlow && query.flow && <option value={query.flow}>{query.flow.slice(0, 8)}</option>}
          {flowOptions.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name}
            </option>
          ))}
        </select>
        <label htmlFor="status" className="sr-only">
          Status
        </label>
        <select id="status" name="status" defaultValue={query.status ?? ""} className={SELECT}>
          <option value="">Status: All</option>
          <option value="succeeded">Succeeded</option>
          <option value="failed">Failed</option>
        </select>
        <label htmlFor="type" className="sr-only">
          Type
        </label>
        <select id="type" name="type" defaultValue={query.type ?? ""} className={SELECT}>
          <option value="">Type: All</option>
          <option value="live">Live</option>
          <option value="test">Test</option>
        </select>
        <button type="submit" className={cn(buttonVariants({ variant: "outline" }), "h-10")}>
          Apply
        </button>
        {filtered && (
          <Link href="/runs" className={cn(buttonVariants({ variant: "ghost" }), "h-10")}>
            Clear filters
          </Link>
        )}
      </form>

      {!flows.ok && (
        <p role="status" className="text-sm text-muted-foreground">
          Flow names could not be loaded; showing ids instead.
        </p>
      )}

      {!runs.ok ? (
        <p role="alert" className="flex items-center gap-2 rounded-xl border p-4 text-sm">
          <CircleX className="size-4 text-red-600 dark:text-red-400" aria-hidden />
          {isUnreachable(runs.error)
            ? UNREACHABLE_MESSAGE
            : `Could not load runs: ${errorText(runs.error)}`}
          <RetryButton />
        </p>
      ) : runs.data.items.length === 0 ? (
        <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
          {filtered || query.cursor
            ? "No runs match these filters."
            : "No runs yet. Run a flow from the editor and it will show up here."}
        </div>
      ) : (
        <>
          <div className="rounded-xl border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Run</TableHead>
                  <TableHead>Flow</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Started</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.data.items.map((run) => {
                  const name = flowNames.get(run.flow_id);
                  return (
                    <TableRow key={run.run_id}>
                      <TableCell className="font-mono text-xs">{run.run_id.slice(0, 8)}</TableCell>
                      <TableCell className="font-medium">
                        <Link href={`/flows/${run.flow_id}`} className="hover:underline">
                          {name ?? run.flow_id.slice(0, 8)}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <RunStatus run={run} />
                      </TableCell>
                      <TableCell>{run.test && <Badge variant="outline">Test</Badge>}</TableCell>
                      <TableCell className="text-muted-foreground">{formatDuration(run.duration_ms)}</TableCell>
                      <TableCell className="text-muted-foreground">{formatDateTime(run.started_at)}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
          <Pager query={query} nextCursor={runs.data.next_cursor} />
        </>
      )}
    </div>
  );
}

function PagerLink({ href, children }: { href: string | null; children: React.ReactNode }) {
  const link = cn(buttonVariants({ variant: "outline" }), "h-10");
  return href ? (
    <Link href={href} className={link}>
      {children}
    </Link>
  ) : (
    <span aria-disabled="true" className={cn(link, "pointer-events-none opacity-50")}>
      {children}
    </span>
  );
}

function Pager({ query, nextCursor }: { query: RunsQuery; nextCursor: string | null | undefined }) {
  return (
    <div className="flex items-center justify-between text-sm text-muted-foreground">
      <span>{PAGE_SIZE} per page · newest first</span>
      <div className="flex gap-2">
        <PagerLink href={newerHref(query)}>
          <ChevronLeft aria-hidden /> Newer
        </PagerLink>
        <PagerLink href={nextCursor ? olderHref(query, nextCursor) : null}>
          Older <ChevronRight aria-hidden />
        </PagerLink>
      </div>
    </div>
  );
}
