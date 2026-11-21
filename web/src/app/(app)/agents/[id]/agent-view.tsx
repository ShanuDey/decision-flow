"use client";

import { useState } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { AgentSummary, ThreadSummary } from "@/lib/api/models";
import type { AgentForm } from "@/lib/agents";
import type { ConnectionOption } from "@/lib/connections";
import { lacksBaseUrl } from "@/lib/graph/prompt";
import type { PublishedFlow } from "@/lib/graph/subflow";

import { AgentChat } from "./agent-chat";
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
  if (!agent.connection_id) return "This agent has no connection yet. Pick one in Settings.";
  const chosen = connections.find((c) => c.id === agent.connection_id);
  if (!chosen) return "This agent's connection no longer exists. Pick another in Settings.";
  if (lacksBaseUrl(chosen)) return "This agent's connection has no base URL. Pick an OpenAI-compatible one in Settings.";
  return null;
}

export function AgentView({
  agent,
  connections,
  flows,
  threads,
}: {
  agent: AgentSummary;
  connections: ConnectionOption[];
  flows: PublishedFlow[];
  threads: ThreadSummary[];
}) {
  const problem = readiness(agent, connections);
  const [tab, setTab] = useState(problem ? "settings" : "chat");

  return (
    <Tabs value={tab} onValueChange={(value) => setTab(String(value))} className="gap-4">
      <TabsList>
        <TabsTrigger value="chat">Chat</TabsTrigger>
        <TabsTrigger value="settings">Settings</TabsTrigger>
      </TabsList>
      <TabsContent value="chat">
        <AgentChat
          agentId={agent.id}
          problem={problem}
          initialThreads={threads}
          onOpenSettings={() => setTab("settings")}
        />
      </TabsContent>
      <TabsContent value="settings">
        <AgentSettings id={agent.id} initial={formOf(agent)} connections={connections} flows={flows} />
      </TabsContent>
    </Tabs>
  );
}
