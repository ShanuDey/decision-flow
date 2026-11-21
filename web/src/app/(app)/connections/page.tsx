import { CircleX } from "lucide-react";
import type { Metadata } from "next";

import { RetryButton } from "@/components/retry-button";
import { listConnections, listConnectionTypes } from "@/lib/api/client";
import { serverApiInit } from "@/lib/auth/session";
import { call, errorText, isUnreachable, UNREACHABLE_MESSAGE } from "@/lib/call";
import { parsePrefill } from "@/lib/connections";

import { ConnectionsPanel } from "./connections-panel";

export const metadata: Metadata = { title: "Connections · Decision Flow" };
export const maxDuration = 60;

export default async function ConnectionsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const init = await serverApiInit();
  const [connections, types] = await Promise.all([
    call(listConnections(init)),
    call(listConnectionTypes(init)),
  ]);

  const failure = !connections.ok ? connections.error : !types.ok ? types.error : null;
  if (failure || !connections.ok || !types.ok) {
    return (
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <h1 className="text-2xl font-semibold tracking-tight">Connections</h1>
        <p role="alert" className="flex items-center gap-2 rounded-xl border p-4 text-sm">
          <CircleX className="size-4 text-red-600 dark:text-red-400" aria-hidden />
          {failure && isUnreachable(failure)
            ? UNREACHABLE_MESSAGE
            : `Could not load connections: ${failure ? errorText(failure) : "unknown error"}`}
          <RetryButton />
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">Connections</h1>
      <ConnectionsPanel
        connections={connections.data.items}
        types={types.data.items}
        prefill={parsePrefill(params, types.data.items)}
      />
    </div>
  );
}
