import { CircleX } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { RetryButton } from "@/components/retry-button";
import { Badge } from "@/components/ui/badge";
import { listFlows } from "@/lib/api/client";
import { ListFlowsSort, type FlowSummary } from "@/lib/api/models";
import { requireSession, serverApiInit } from "@/lib/auth/session";
import { call, errorText, isUnreachable, UNREACHABLE_MESSAGE } from "@/lib/call";
import { formatDateTime } from "@/lib/format";

import { NewFlowButton } from "../flows/new-flow-button";

export const metadata: Metadata = { title: "Overview · Decision Flow" };
export const maxDuration = 60;

const RECENT = 5;

export default async function OverviewPage() {
  const { user } = await requireSession();
  const result = await call(
    listFlows(
      { sort: "-updated_at" as ListFlowsSort, page: 1, page_size: RECENT },
      await serverApiInit(),
    ),
  );
  const firstName = user.name?.trim().split(/\s+/)[0] || null;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {firstName ? `Welcome back, ${firstName}` : "Welcome back"}
          </h1>
          <p className="text-sm text-muted-foreground">Here is what is happening in your workspace.</p>
        </div>
        <NewFlowButton />
      </div>

      {!result.ok ? (
        <p role="alert" className="flex items-center gap-2 rounded-xl border p-4 text-sm">
          <CircleX className="size-4 text-red-600 dark:text-red-400" aria-hidden />
          {isUnreachable(result.error)
            ? UNREACHABLE_MESSAGE
            : `Could not load your overview: ${errorText(result.error)}`}
          <RetryButton />
        </p>
      ) : result.data.total === 0 ? (
        <GettingStarted email={user.email} />
      ) : (
        <Summary total={result.data.total} items={result.data.items} />
      )}
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-xl border p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-3xl font-semibold tracking-tight tabular-nums">{value}</p>
      <p className="text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}

function Summary({ total, items }: { total: number; items: FlowSummary[] }) {
  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2">
        <Stat label="Flows" value={String(total)} hint="in your workspace" />
        <Stat label="Last edited" value={formatDateTime(items[0].updated_at)} hint={items[0].name} />
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <section className="rounded-xl border" aria-labelledby="recent-flows">
          <header className="flex items-center justify-between border-b px-4 py-3">
            <h2 id="recent-flows" className="font-semibold">
              Recently edited
            </h2>
            <Link href="/flows" className="text-sm text-muted-foreground hover:underline">
              View all flows
            </Link>
          </header>
          <ul>
            {items.map((flow) => (
              <li key={flow.id} className="flex items-center gap-3 border-b px-4 py-3 last:border-b-0">
                <div className="min-w-0 flex-1">
                  <Link href={`/flows/${flow.id}`} className="block truncate font-medium hover:underline">
                    {flow.name}
                  </Link>
                  <p className="text-sm text-muted-foreground">Draft v{flow.draft_version}</p>
                </div>
                <time dateTime={flow.updated_at} className="text-sm whitespace-nowrap text-muted-foreground">
                  {formatDateTime(flow.updated_at)}
                </time>
              </li>
            ))}
          </ul>
        </section>
        <RunsPanel />
      </div>
    </>
  );
}

function RunsPanel() {
  return (
    <section className="rounded-xl border" aria-labelledby="recent-runs">
      <header className="flex items-center justify-between border-b px-4 py-3">
        <h2 id="recent-runs" className="font-semibold">
          Recent runs
        </h2>
        <Badge variant="secondary">Soon</Badge>
      </header>
      <p className="m-4 rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
        Runs will appear here once running flows is available.
      </p>
    </section>
  );
}

const STEPS = [
  { title: "Create your first flow", hint: "It starts with a Start and an End node." },
  { title: "Build the logic", hint: "Add nodes, connect branches, and edit expressions." },
  { title: "Run it", hint: "Run it with real input." },
];

function GettingStarted({ email }: { email: string }) {
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
      <section className="rounded-xl border" aria-labelledby="get-started">
        <header className="border-b px-4 py-3">
          <h2 id="get-started" className="font-semibold">
            Get started
          </h2>
        </header>
        <ol className="flex flex-col gap-3 p-4">
          <li className="flex gap-3 text-sm">
            <span
              aria-hidden
              className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-primary text-xs text-primary-foreground"
            >
              ✓
            </span>
            <div>
              <p className="font-medium">Create your account</p>
              <p className="text-muted-foreground">You are signed in as {email}.</p>
            </div>
          </li>
          {STEPS.map((step) => (
            <li key={step.title} className="flex gap-3 text-sm">
              <span aria-hidden className="mt-0.5 size-5 shrink-0 rounded-full border-2" />
              <div>
                <p className="font-medium">{step.title}</p>
                <p className="text-muted-foreground">{step.hint}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
      <RunsPanel />
    </div>
  );
}
