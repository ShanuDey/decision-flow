"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { updateAgent } from "@/lib/api/client";
import type { AgentSummary, ThreadSummary } from "@/lib/api/models";
import { errorToast } from "@/lib/api-error";
import { type AgentForm, formProblem, sameForm, updateBody } from "@/lib/agents";
import { call } from "@/lib/call";
import type { ConnectionOption } from "@/lib/connections";
import { lacksBaseUrl } from "@/lib/graph/prompt";
import type { PublishedFlow } from "@/lib/graph/subflow";

import { AgentChats } from "./agent-chats";
import { AgentSettings } from "./agent-settings";

export function formOf(agent: AgentSummary): AgentForm {
  return {
    name: agent.name,
    description: agent.description ?? "",
    connection_id: agent.connection_id ?? "",
    model: agent.model ?? "",
    instructions: agent.instructions ?? "",
    tools: (agent.tools ?? []).map((t) => ({
      flow_id: t.flow_id ?? "",
      name: t.name ?? "",
      description: t.description ?? "",
    })),
    max_iterations: agent.max_iterations ?? 8,
    max_total_tokens: agent.max_total_tokens ?? null,
    max_seconds: agent.max_seconds ?? null,
    temperature: agent.temperature ?? null,
    max_tokens: agent.max_tokens ?? null,
    timeout_seconds: agent.timeout_seconds ?? null,
  };
}

function readiness(agent: AgentSummary, connections: ConnectionOption[]): string | null {
  if (!agent.connection_id) return "This agent has no connection yet. Pick one in Configure.";
  const chosen = connections.find((c) => c.id === agent.connection_id);
  if (!chosen) return "This agent's connection no longer exists. Pick another in Configure.";
  if (lacksBaseUrl(chosen)) return "This agent's connection has no base URL. Pick an OpenAI-compatible one in Configure.";
  return null;
}

export function AgentView({
  agent,
  connections,
  flows,
  threads: initialThreads,
  initialThreadId,
}: {
  agent: AgentSummary;
  connections: ConnectionOption[];
  flows: PublishedFlow[];
  threads: ThreadSummary[];
  initialThreadId?: string;
}) {
  const router = useRouter();
  const problem = readiness(agent, connections);
  const [tab, setTab] = useState(problem ? "configure" : "chats");
  const [saved, setSaved] = useState(() => formOf(agent));
  const [form, setForm] = useState(saved);
  const [busy, setBusy] = useState(false);
  const [threads, setThreads] = useState(initialThreads);
  const [activeId, setActiveId] = useState<string | null>(
    initialThreads.find((t) => t.id === initialThreadId)?.id ?? initialThreads[0]?.id ?? null,
  );
  const set = (change: Partial<AgentForm>) => setForm((f) => ({ ...f, ...change }));
  const dirty = !sameForm(form, saved);
  const invalid = formProblem(form);

  async function save() {
    setBusy(true);
    const result = await call(updateAgent(agent.id, updateBody(form)));
    setBusy(false);
    if (!result.ok) {
      errorToast("Could not save the agent", result.error);
      return;
    }
    setSaved(form);
    toast.success("Saved");
    router.refresh();
  }

  return (
    <Tabs value={tab} onValueChange={(value) => setTab(String(value))} className="gap-3">
      <div className="grid items-center gap-3 md:grid-cols-[1fr_auto_1fr]">
        <h1 className="flex min-w-0 items-baseline gap-2 text-base font-semibold">
          <Link href="/agents" className="text-sm font-normal text-muted-foreground underline-offset-2 hover:underline">
            Agents /
          </Link>
          <span className="truncate">{agent.name}</span>
        </h1>
        <TabsList className="justify-self-start md:justify-self-center">
          <TabsTrigger value="configure">Configure</TabsTrigger>
          <TabsTrigger value="chats">Chats</TabsTrigger>
        </TabsList>
        <div className="flex items-center justify-end gap-3">
          {dirty && (
            <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
              <span className="size-2 rounded-full bg-amber-400" aria-hidden />
              {invalid ?? "Unsaved changes"}
            </span>
          )}
          <Button className="h-9" disabled={busy || !dirty || invalid !== null} onClick={() => void save()}>
            {busy ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
      <TabsContent value="configure">
        <AgentSettings form={form} set={set} connections={connections} flows={flows} />
      </TabsContent>
      <TabsContent value="chats">
        <AgentChats
          agentId={agent.id}
          agentName={agent.name}
          problem={problem}
          threads={threads}
          setThreads={setThreads}
          activeId={activeId}
          setActiveId={setActiveId}
        />
      </TabsContent>
    </Tabs>
  );
}
