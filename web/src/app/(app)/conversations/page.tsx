import { CircleX } from "lucide-react";
import type { Metadata } from "next";

import { RetryButton } from "@/components/retry-button";
import { listAgents, listWorkspaceThreads } from "@/lib/api/client";
import { serverApiInit } from "@/lib/auth/session";
import { call, errorText, isUnreachable, UNREACHABLE_MESSAGE } from "@/lib/call";

import { ConversationsView } from "./conversations-view";

export const metadata: Metadata = { title: "Conversations · Decision Flow" };
export const maxDuration = 60;

const LIMIT = 100;

export default async function ConversationsPage() {
  const init = await serverApiInit();
  const [agents, threads] = await Promise.all([
    call(listAgents(init)),
    call(listWorkspaceThreads({ limit: LIMIT }, init)),
  ]);

  if (!agents.ok || !threads.ok) {
    const failure = !agents.ok ? agents.error : !threads.ok ? threads.error : null;
    return (
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <h1 className="text-2xl font-semibold tracking-tight">Conversations</h1>
        <p role="alert" className="flex items-center gap-2 rounded-xl border p-4 text-sm">
          <CircleX className="size-4 text-red-600 dark:text-red-400" aria-hidden />
          {failure && isUnreachable(failure)
            ? UNREACHABLE_MESSAGE
            : `Could not load conversations: ${failure ? errorText(failure) : "unknown error"}`}
          <RetryButton />
        </p>
      </div>
    );
  }

  return <ConversationsView agents={agents.data.items} threads={threads.data.items} limit={LIMIT} />;
}
