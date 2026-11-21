"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SelectField } from "@/components/ui/select-field";
import { Textarea } from "@/components/ui/textarea";
import { Labeled, ListEditor, patch } from "@/components/editor/fields";
import { NumberField } from "@/components/editor/prompt-form";
import { updateAgent } from "@/lib/api/client";
import { errorToast } from "@/lib/api-error";
import { call } from "@/lib/call";
import { type AgentForm, formProblem, sameForm, updateBody } from "@/lib/agents";
import type { ConnectionOption } from "@/lib/connections";
import { parseIterations, parseMaxSeconds, toolNameProblem } from "@/lib/graph/agent";
import { parseTimeout } from "@/lib/graph/http-request";
import { lacksBaseUrl, parseMaxTokens, parseTemperature, promptConnections } from "@/lib/graph/prompt";
import type { PublishedFlow } from "@/lib/graph/subflow";

function toolName(flowName: string): string {
  return flowName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 64);
}

export function AgentSettings({
  id,
  initial,
  connections,
  flows,
}: {
  id: string;
  initial: AgentForm;
  connections: ConnectionOption[];
  flows: PublishedFlow[];
}) {
  const router = useRouter();
  const [saved, setSaved] = useState(initial);
  const [form, setForm] = useState(initial);
  const [busy, setBusy] = useState(false);
  const set = (change: Partial<AgentForm>) => setForm((f) => ({ ...f, ...change }));
  const problem = formProblem(form);
  const dirty = !sameForm(form, saved);
  const chosen = connections.find((c) => c.id === form.connection_id);
  const names = form.tools.map((t) => t.name);

  async function save() {
    setBusy(true);
    const result = await call(updateAgent(id, updateBody(form)));
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
    <div className="flex max-w-2xl flex-col gap-8">
      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium">Agent</h2>
        <Labeled id="agent-name" label="Name">
          <Input id="agent-name" className="h-10" value={form.name} maxLength={80} onChange={(e) => set({ name: e.target.value })} />
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
        <Labeled id="agent-instructions" label="Instructions">
          <Textarea
            id="agent-instructions"
            rows={6}
            value={form.instructions}
            placeholder="You help support staff. Use the tools before you answer."
            onChange={(e) => set({ instructions: e.target.value })}
          />
        </Labeled>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium">Model</h2>
        <Labeled id="agent-connection" label="Connection">
          <SelectField
            id="agent-connection"
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
            className="h-10"
            value={form.model}
            placeholder="Empty uses the connection's default model"
            onChange={(e) => set({ model: e.target.value })}
          />
        </Labeled>
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
      </section>

      <ListEditor
        title="Tools (flows the agent can run)"
        items={form.tools}
        addLabel="Add tool"
        emptyText="No tools yet. Without tools the agent can only answer from its instructions and the conversation."
        onAdd={() => set({ tools: [...form.tools, { flow_id: "", name: "", description: "" }] })}
        onRemove={(i) => set({ tools: form.tools.filter((_, j) => j !== i) })}
        renderItem={(tool, i) => {
          const base = `agent-tool-${i}`;
          const nameProblem = toolNameProblem(names, i);
          const known = flows.some((f) => f.id === tool.flow_id);
          return (
            <>
              <Labeled id={`${base}-flow`} label="Published flow">
                <SelectField
                  id={`${base}-flow`}
                  value={tool.flow_id}
                  placeholder="Select a flow…"
                  onValueChange={(flow_id) => {
                    const flow = flows.find((f) => f.id === flow_id);
                    set({
                      tools: patch(form.tools, i, {
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
              <Labeled id={`${base}-name`} label="Tool name">
                <Input
                  id={`${base}-name`}
                  className="h-10 font-mono text-xs"
                  value={tool.name}
                  placeholder="lookup_order"
                  autoComplete="off"
                  spellCheck={false}
                  aria-invalid={nameProblem !== null && tool.name !== ""}
                  onChange={(e) => set({ tools: patch(form.tools, i, { name: e.target.value }) })}
                />
                {nameProblem && tool.name !== "" && (
                  <p role="alert" className="text-xs text-red-700 dark:text-red-400">
                    {nameProblem}
                  </p>
                )}
              </Labeled>
              <Labeled id={`${base}-description`} label="What it does and when to use it">
                <Textarea
                  id={`${base}-description`}
                  rows={3}
                  value={tool.description}
                  placeholder="Returns the status and ship date of an order. Needs the order id."
                  onChange={(e) => set({ tools: patch(form.tools, i, { description: e.target.value }) })}
                />
              </Labeled>
            </>
          );
        }}
      />

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium">Limits for one answer</h2>
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
        <p className="text-xs text-muted-foreground">
          A message fails if a limit is reached before the agent answers. Flows it already ran are not undone.
        </p>
      </section>

      <div className="sticky bottom-0 flex flex-wrap items-center gap-3 border-t bg-background py-3">
        <Button className="h-10" disabled={busy || !dirty || problem !== null} onClick={() => void save()}>
          {busy ? "Saving…" : "Save"}
        </Button>
        {problem && dirty && <p className="text-sm text-red-700 dark:text-red-400">{problem}</p>}
        {!dirty && <p className="text-sm text-muted-foreground">No changes</p>}
      </div>
    </div>
  );
}
