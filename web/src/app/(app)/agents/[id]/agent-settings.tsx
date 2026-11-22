"use client";

import { Plus, Trash2 } from "lucide-react";
import { type ReactNode, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SelectField } from "@/components/ui/select-field";
import { Textarea } from "@/components/ui/textarea";
import { Labeled, patch } from "@/components/editor/fields";
import { NumberField } from "@/components/editor/prompt-form";
import type { AgentForm } from "@/lib/agents";
import type { ConnectionOption } from "@/lib/connections";
import { parseIterations, parseMaxSeconds, toolNameProblem } from "@/lib/graph/agent";
import { parseTimeout } from "@/lib/graph/http-request";
import { lacksBaseUrl, parseMaxTokens, parseTemperature, promptConnections } from "@/lib/graph/prompt";
import type { PublishedFlow } from "@/lib/graph/subflow";
import { cn } from "@/lib/utils";

function toolName(flowName: string): string {
  return flowName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 64);
}

type SectionId = "agent" | "model" | "tools" | "limits";

function Section({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="flex flex-col gap-5">
      <div>
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      {children}
    </section>
  );
}

function ToolsPane({
  form,
  set,
  flows,
}: {
  form: AgentForm;
  set: (change: Partial<AgentForm>) => void;
  flows: PublishedFlow[];
}) {
  const [picked, setPicked] = useState(0);
  const names = form.tools.map((t) => t.name);
  const index = Math.min(picked, form.tools.length - 1);
  const tool = form.tools[index];

  function add() {
    set({ tools: [...form.tools, { flow_id: "", name: "", description: "" }] });
    setPicked(form.tools.length);
  }

  function remove(i: number) {
    set({ tools: form.tools.filter((_, j) => j !== i) });
    setPicked(Math.max(0, i - 1));
  }

  const nameProblem = tool ? toolNameProblem(names, index) : null;
  const known = tool ? flows.some((f) => f.id === tool.flow_id) : true;

  return (
    <div className="grid gap-4 md:grid-cols-[16rem_minmax(0,1fr)]">
      <div className="flex flex-col gap-2">
        <Button type="button" variant="outline" className="h-10 justify-start gap-2" onClick={add}>
          <Plus aria-hidden /> Add tool
        </Button>
        <ul aria-label="Tools" className="flex flex-col gap-0.5">
          {form.tools.map((t, i) => (
            <li key={i}>
              <button
                type="button"
                aria-current={i === index ? "true" : undefined}
                onClick={() => setPicked(i)}
                className={cn(
                  "flex w-full min-w-0 flex-col rounded-lg px-3 py-2 text-left outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50",
                  i === index && "bg-muted",
                )}
              >
                <span className="truncate text-sm font-medium">{t.name || "Unnamed tool"}</span>
                <span className="truncate text-xs text-muted-foreground">
                  {flows.find((f) => f.id === t.flow_id)?.name ?? "No flow chosen"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>

      {tool ? (
        <div className="flex min-w-0 flex-col gap-5 rounded-xl border p-5">
          <div className="flex items-center justify-between gap-3">
            <h3 className="truncate font-semibold">{tool.name || "Unnamed tool"}</h3>
            <Button type="button" variant="ghost" size="sm" className="gap-1.5" onClick={() => remove(index)}>
              <Trash2 aria-hidden /> Remove
            </Button>
          </div>
          <Labeled id="tool-flow" label="Published flow">
            <SelectField
              id="tool-flow"
              value={tool.flow_id}
              placeholder="Select a flow…"
              onValueChange={(flow_id) => {
                const flow = flows.find((f) => f.id === flow_id);
                set({
                  tools: patch(form.tools, index, {
                    flow_id,
                    name: tool.name || (flow ? toolName(flow.name) : ""),
                  }),
                });
              }}
              options={[
                ...(tool.flow_id && !known ? [{ value: tool.flow_id, label: "Unavailable flow" }] : []),
                ...flows.map((f) => ({ value: f.id, label: `${f.name} (v${f.version})` })),
              ]}
            />
          </Labeled>
          <Labeled id="tool-name" label="Tool name">
            <Input
              id="tool-name"
              className="h-10 max-w-md font-mono text-xs"
              value={tool.name}
              placeholder="lookup_order"
              autoComplete="off"
              spellCheck={false}
              aria-invalid={nameProblem !== null && tool.name !== ""}
              onChange={(e) => set({ tools: patch(form.tools, index, { name: e.target.value }) })}
            />
            {nameProblem && tool.name !== "" && (
              <p role="alert" className="text-xs text-red-700 dark:text-red-400">
                {nameProblem}
              </p>
            )}
          </Labeled>
          <Labeled id="tool-description" label="What it does and when to use it">
            <Textarea
              id="tool-description"
              className="min-h-32"
              value={tool.description}
              placeholder="Returns the status and ship date of an order. Needs the order id."
              onChange={(e) => set({ tools: patch(form.tools, index, { description: e.target.value }) })}
            />
          </Labeled>
        </div>
      ) : (
        <p className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
          No tools yet. Without tools the agent can only answer from its instructions and the conversation.
        </p>
      )}
    </div>
  );
}

export function AgentSettings({
  form,
  set,
  connections,
  flows,
}: {
  form: AgentForm;
  set: (change: Partial<AgentForm>) => void;
  connections: ConnectionOption[];
  flows: PublishedFlow[];
}) {
  const [section, setSection] = useState<SectionId>("agent");
  const chosen = connections.find((c) => c.id === form.connection_id);
  const sections: { id: SectionId; label: string; count?: number }[] = [
    { id: "agent", label: "Agent" },
    { id: "model", label: "Model" },
    { id: "tools", label: "Tools", count: form.tools.length },
    { id: "limits", label: "Limits" },
  ];

  return (
    <div className="grid gap-6 lg:grid-cols-[13rem_minmax(0,1fr)] lg:gap-10">
      <nav aria-label="Configure" className="flex gap-1 overflow-x-auto lg:sticky lg:top-4 lg:flex-col lg:self-start">
        {sections.map((s) => (
          <button
            key={s.id}
            type="button"
            aria-current={section === s.id ? "page" : undefined}
            onClick={() => setSection(s.id)}
            className={cn(
              "flex shrink-0 items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm font-medium outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50",
              section === s.id ? "bg-muted text-foreground" : "text-muted-foreground",
            )}
          >
            {s.label}
            {s.count !== undefined && s.count > 0 && (
              <span className="rounded-full bg-background px-2 text-xs tabular-nums">{s.count}</span>
            )}
          </button>
        ))}
      </nav>

      <div className="min-w-0 max-w-6xl pb-8">
        {section === "agent" && (
          <Section title="Agent" description="Who the agent is and how it should behave.">
            <Labeled id="agent-name" label="Name">
              <Input id="agent-name" className="h-10 max-w-md" value={form.name} maxLength={80} onChange={(e) => set({ name: e.target.value })} />
            </Labeled>
            <Labeled id="agent-description" label="Description (optional)">
              <Input
                id="agent-description"
                className="h-10"
                value={form.description}
                maxLength={500}
                onChange={(e) => set({ description: e.target.value })}
              />
            </Labeled>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="agent-instructions" className="text-sm font-medium">
                Instructions
              </label>
              <Textarea
                id="agent-instructions"
                className="min-h-72"
                value={form.instructions}
                placeholder="You help support staff. Use the tools before you answer."
                onChange={(e) => set({ instructions: e.target.value })}
              />
              <p className="text-xs text-muted-foreground">
                Sent with every message. Say what the agent is for, when to use each tool, and how to answer.
              </p>
            </div>
          </Section>
        )}

        {section === "model" && (
          <Section title="Model" description="Which provider answers, and how it is called.">
            <Labeled id="agent-connection" label="Connection">
              <SelectField
                id="agent-connection"
                className="max-w-md"
                value={chosen ? chosen.id : ""}
                placeholder="Select a connection…"
                onValueChange={(connection_id) => set({ connection_id })}
                options={promptConnections(connections, form.connection_id).map((c) => ({
                  value: c.id,
                  label: `${c.name} (${c.typeName})`,
                }))}
              />
            </Labeled>
            {form.connection_id !== "" && !chosen && (
              <p role="alert" className="text-xs text-red-700 dark:text-red-400">
                The saved connection no longer exists. Pick another, or the agent cannot answer.
              </p>
            )}
            {lacksBaseUrl(chosen) && (
              <p role="alert" className="text-xs text-red-700 dark:text-red-400">
                This connection has no base URL. Pick an OpenAI-compatible connection.
              </p>
            )}
            {connections.length === 0 && (
              <p className="text-xs text-muted-foreground">
                No connections yet.{" "}
                <a href="/connections" className="underline underline-offset-2 hover:text-foreground">
                  Add one
                </a>{" "}
                to use a model.
              </p>
            )}
            <Labeled id="agent-model" label="Model (optional)">
              <Input
                id="agent-model"
                className="h-10 max-w-md"
                value={form.model}
                placeholder="Empty uses the connection's default model"
                onChange={(e) => set({ model: e.target.value })}
              />
            </Labeled>
            <div className="grid gap-4 sm:grid-cols-3">
              <NumberField
                id="agent-temperature"
                label="Temperature (0 to 2)"
                value={form.temperature}
                placeholder="Provider default"
                parse={parseTemperature}
                onValue={(temperature) => set({ temperature })}
              />
              <NumberField
                id="agent-max-tokens"
                label="Max tokens per model call"
                value={form.max_tokens}
                placeholder="Provider default"
                parse={parseMaxTokens}
                onValue={(max_tokens) => set({ max_tokens })}
              />
              <NumberField
                id="agent-timeout"
                label="Timeout per model call (seconds)"
                value={form.timeout_seconds}
                placeholder="Server default"
                parse={parseTimeout}
                onValue={(timeout_seconds) => set({ timeout_seconds })}
              />
            </div>
          </Section>
        )}

        {section === "tools" && (
          <Section title="Tools" description="Published flows the agent can run while it answers.">
            <ToolsPane form={form} set={set} flows={flows} />
          </Section>
        )}

        {section === "limits" && (
          <Section title="Limits" description="Caps for one answer, so a runaway loop stops.">
            <div className="grid gap-4 sm:grid-cols-3">
              <NumberField
                id="agent-iterations"
                label="Max iterations (model calls)"
                value={form.max_iterations}
                placeholder="8"
                parse={parseIterations}
                onValue={(value) => value !== null && set({ max_iterations: value })}
              />
              <NumberField
                id="agent-total-tokens"
                label="Max total tokens"
                value={form.max_total_tokens}
                placeholder="No limit"
                parse={parseMaxTokens}
                onValue={(max_total_tokens) => set({ max_total_tokens })}
              />
              <NumberField
                id="agent-seconds"
                label="Max seconds"
                value={form.max_seconds}
                placeholder="120"
                parse={parseMaxSeconds}
                onValue={(max_seconds) => set({ max_seconds })}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              A message fails if a limit is reached before the agent answers. Flows it already ran are not undone.
            </p>
          </Section>
        )}
      </div>
    </div>
  );
}
