import { CircleX } from "lucide-react";
import type { Metadata } from "next";

import { RetryButton } from "@/components/retry-button";
import { listAgents, listConnections } from "@/lib/api/client";
import { serverApiInit } from "@/lib/auth/session";
import { call, errorText, isUnreachable, UNREACHABLE_MESSAGE } from "@/lib/call";

import { AgentsPanel } from "./agents-panel";

export const metadata: Metadata = { title: "Agents · Decision Flow" };
export const maxDuration = 60;

export default async function AgentsPage() {
  const init = await serverApiInit();
  const [agents, connections] = await Promise.all([call(listAgents(init)), call(listConnections(init))]);

  if (!agents.ok || !connections.ok) {
    const failure = !agents.ok ? agents.error : !connections.ok ? connections.error : null;
    return (
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <h1 className="text-2xl font-semibold tracking-tight">Agents</h1>
        <p role="alert" className="flex items-center gap-2 rounded-xl border p-4 text-sm">
          <CircleX className="size-4 text-red-600 dark:text-red-400" aria-hidden />
          {failure && isUnreachable(failure)
            ? UNREACHABLE_MESSAGE
            : `Could not load agents: ${failure ? errorText(failure) : "unknown error"}`}
          <RetryButton />
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">Agents</h1>
      <AgentsPanel
        agents={agents.data.items}
        connectionNames={Object.fromEntries(connections.data.items.map((c) => [c.id, c.name]))}
      />
    </div>
  );
}
