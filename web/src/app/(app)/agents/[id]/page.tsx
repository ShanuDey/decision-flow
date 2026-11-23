import { CircleX } from "lucide-react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { RetryButton } from "@/components/retry-button";
import { getAgent, listConnections, listConnectionTypes, listFlows, listThreads } from "@/lib/api/client";
import { serverApiInit } from "@/lib/auth/session";
import { call, errorText, isUnreachable, UNREACHABLE_MESSAGE } from "@/lib/call";
import { connectionOptions } from "@/lib/connections";
import { publishedPage } from "@/lib/graph/subflow";

import { AgentView } from "./agent-view";

export const metadata: Metadata = { title: "Agent · Decision Flow" };
export const maxDuration = 60;

const FLOW_PAGE = 100;

export default async function AgentPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ thread?: string }>;
}) {
  const { id } = await params;
  const { thread } = await searchParams;
  const init = await serverApiInit();
  const [agent, connections, types, flows, threads] = await Promise.all([
    call(getAgent(id, init)),
    call(listConnections(init)),
    call(listConnectionTypes(init)),
    call(listFlows({ sort: "name", page_size: FLOW_PAGE }, init)),
    call(listThreads(id, undefined, init)),
  ]);

  if (!agent.ok && (agent.error.status === 404 || agent.error.status === 422)) notFound();
  if (!agent.ok || !connections.ok || !types.ok || !flows.ok || !threads.ok) {
    const failure = [agent, connections, types, flows, threads].flatMap((r) => (r.ok ? [] : [r.error]))[0];
    return (
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <p role="alert" className="flex items-center gap-2 rounded-xl border p-4 text-sm">
          <CircleX className="size-4 text-red-600 dark:text-red-400" aria-hidden />
          {failure && isUnreachable(failure)
            ? UNREACHABLE_MESSAGE
            : `Could not load the agent: ${failure ? errorText(failure) : "unknown error"}`}
          <RetryButton />
        </p>
      </div>
    );
  }

  return (
    <div className="flex w-full flex-col gap-4">
      <AgentView
        key={agent.data.id}
        agent={agent.data}
        connections={connectionOptions(connections.data.items, types.data.items)}
        flows={publishedPage(flows.data.items, flows.data.total).flows}
        threads={threads.data.items}
        initialThreadId={thread}
      />
    </div>
  );
}
