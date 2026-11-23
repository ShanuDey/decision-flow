"use client";

import { Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { TraceDialog } from "@/components/trace/trace-dialog";
import { buttonVariants } from "@/components/ui/button";
import { SelectField } from "@/components/ui/select-field";
import { getMessageSteps } from "@/lib/api/client";
import type { AgentSummary, ThreadSummary } from "@/lib/api/models";
import { groupByAgent, whoKind, type WhoKind, whoLabel } from "@/lib/agents";
import { call } from "@/lib/call";
import { parseApiDate } from "@/lib/format";
import { cn } from "@/lib/utils";

import { AgentRuntime } from "../agents/[id]/agent-runtime";
import { AgentThread } from "../agents/[id]/agent-thread";

const WHO: { value: "all" | WhoKind; label: string }[] = [
  { value: "all", label: "All" },
  { value: "team", label: "Team" },
  { value: "external", label: "External" },
  { value: "anonymous", label: "Anonymous" },
];

const noop = () => {};

function when(iso: string): string {
  const date = parseApiDate(iso);
  const sameDay = date.toDateString() === new Date().toDateString();
  return sameDay
    ? date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString([], { day: "numeric", month: "short" });
}

export function ConversationsView({
  agents,
  threads,
  limit,
}: {
  agents: AgentSummary[];
  threads: ThreadSummary[];
  limit: number;
}) {
  const [query, setQuery] = useState("");
  const [agentId, setAgentId] = useState("");
  const [who, setWho] = useState<"all" | WhoKind>("all");
  const [picked, setPicked] = useState<string | null>(null);
  const [traceId, setTraceId] = useState<string | null>(null);

  const names = useMemo(() => Object.fromEntries(agents.map((a) => [a.id, a.name])), [agents]);
  const shown = useMemo(() => {
    const term = query.trim().toLowerCase();
    return threads.filter(
      (t) =>
        (agentId === "" || t.agent_id === agentId) &&
        (who === "all" || whoKind(t) === who) &&
        (term === "" || (t.title || "New chat").toLowerCase().includes(term)),
    );
  }, [threads, query, agentId, who]);
  const groups = useMemo(() => groupByAgent(shown, names), [shown, names]);
  const selected = shown.find((t) => t.id === picked) ?? shown[0];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-2 text-xl font-semibold tracking-tight">Conversations</h1>
        <label className="flex h-9 w-60 items-center gap-2 rounded-lg bg-muted/60 px-3 text-muted-foreground focus-within:ring-3 focus-within:ring-ring/40">
          <Search className="size-4 shrink-0" aria-hidden />
          <input
            type="search"
            aria-label="Search conversations"
            placeholder="Search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full min-w-0 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
          />
        </label>
        <SelectField
          className="h-9 w-48"
          value={agentId}
          onValueChange={setAgentId}
          options={[{ value: "", label: "All agents" }, ...agents.map((a) => ({ value: a.id, label: a.name }))]}
        />
        <div role="group" aria-label="Who" className="flex gap-0.5 rounded-lg bg-muted p-[3px] text-sm">
          {WHO.map((option) => (
            <button
              key={option.value}
              type="button"
              aria-pressed={who === option.value}
              onClick={() => setWho(option.value)}
              className={cn(
                "rounded-md px-3 py-1 font-medium outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                who === option.value ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {threads.length === 0 ? (
        <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
          No conversations yet. Start one from an agent&apos;s Chats tab, or through the API.
        </p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[380px_minmax(0,1fr)] xl:h-[calc(100dvh-10rem)] xl:min-h-[480px]">
          <aside
            aria-label="Conversations"
            className="flex h-[40dvh] min-h-0 flex-col gap-3 overflow-y-auto rounded-xl border bg-card p-3 xl:h-auto"
          >
            {groups.length === 0 && <p className="px-2 py-1 text-sm text-muted-foreground">No conversations match.</p>}
            {groups.map((group) => (
              <section key={group.agentId} aria-label={group.name} className="flex flex-col gap-0.5">
                <h2 className="px-2 pb-1 text-xs font-medium text-muted-foreground">
                  {group.name} · {group.items.length}
                </h2>
                <ul className="flex flex-col gap-0.5">
                  {group.items.map((thread) => (
                    <li key={thread.id}>
                      <button
                        type="button"
                        aria-current={thread.id === selected?.id ? "true" : undefined}
                        onClick={() => setPicked(thread.id)}
                        className={cn(
                          "flex w-full min-w-0 flex-col rounded-lg px-2.5 py-2 text-left outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50",
                          thread.id === selected?.id && "bg-muted",
                        )}
                      >
                        <span className="flex items-baseline gap-2">
                          <span className="min-w-0 flex-1 truncate text-sm font-medium">{thread.title || "New chat"}</span>
                          <span className="shrink-0 text-xs text-muted-foreground">{when(thread.updated_at)}</span>
                        </span>
                        <span className="truncate text-xs text-muted-foreground">{whoLabel(thread) ?? "Team"}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
            {threads.length >= limit && (
              <p className="px-2 text-xs text-muted-foreground">Showing the {limit} most recent conversations.</p>
            )}
          </aside>

          <section aria-label="Transcript" className="flex h-[70dvh] min-h-0 min-w-0 flex-col rounded-xl border xl:h-auto">
            {selected ? (
              <>
                <div className="flex items-center gap-3 border-b px-5 py-3">
                  <div className="min-w-0">
                    <h2 className="truncate font-semibold">{selected.title || "New chat"}</h2>
                    <p className="truncate text-xs text-muted-foreground">
                      {[
                        names[selected.agent_id],
                        whoLabel(selected) ?? "Team",
                        `Started ${parseApiDate(selected.created_at).toLocaleString()}`,
                      ].join(" · ")}
                    </p>
                  </div>
                  <Link
                    href={`/agents/${selected.agent_id}?thread=${selected.id}`}
                    className={cn(buttonVariants({ variant: "outline" }), "ml-auto h-9")}
                  >
                    Open in agent
                  </Link>
                </div>
                <AgentRuntime key={selected.id} agentId={selected.agent_id} threadId={selected.id} onStored={noop} onError={noop}>
                  <AgentThread
                    agentName={names[selected.agent_id] ?? "Agent"}
                    problem={null}
                    onTrace={setTraceId}
                    readOnly
                  />
                </AgentRuntime>
                {traceId && (
                  <TraceDialog
                    open
                    onOpenChange={(open) => !open && setTraceId(null)}
                    title={selected.title || "New chat"}
                    runId={traceId}
                    fetchSteps={(id) => call(getMessageSteps(selected.agent_id, selected.id, id))}
                  />
                )}
              </>
            ) : (
              <p className="m-auto p-6 text-sm text-muted-foreground">Choose a conversation to read it.</p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
