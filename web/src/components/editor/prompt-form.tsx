"use client";

import { useState } from "react";

import { Input } from "@/components/ui/input";
import { SelectField } from "@/components/ui/select-field";
import type { FlowNode } from "@/lib/graph/convert";
import { parseTimeout } from "@/lib/graph/http-request";
import { lacksBaseUrl, type NumberParse, parseMaxTokens, parseTemperature, promptConnections } from "@/lib/graph/prompt";
import type { PromptData } from "@/lib/graph/types";

import { ExpandableInput } from "./expand-field";
import { Labeled } from "./fields";
import { fieldIssue } from "./issues";
import { useEditor } from "./store";

type Update = (patch: Partial<PromptData>) => void;

export function NumberField({
  id,
  label,
  value,
  placeholder,
  parse,
  onValue,
}: {
  id: string;
  label: string;
  value: number | null;
  placeholder: string;
  parse: (text: string) => NumberParse;
  onValue: (value: number | null) => void;
}) {
  const [text, setText] = useState(value === null ? "" : String(value));
  const parsed = parse(text);
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-xs text-muted-foreground">
        {label}
      </label>
      <Input
        id={id}
        className="h-10"
        inputMode="decimal"
        value={text}
        placeholder={placeholder}
        aria-invalid={!parsed.ok}
        onChange={(e) => {
          setText(e.target.value);
          const next = parse(e.target.value);
          if (next.ok) onValue(next.value);
        }}
      />
      {!parsed.ok && (
        <p role="alert" className="text-xs text-red-700 dark:text-red-400">
          {parsed.error}. The last valid value is kept until this is fixed.
        </p>
      )}
    </div>
  );
}

export function ConnectionField({
  node,
  connectionId,
  onPick,
}: {
  node: FlowNode;
  connectionId: string;
  onPick: (id: string) => void;
}) {
  const connections = useEditor((s) => s.connections);
  const issues = useEditor((s) => s.issues);
  const id = `${node.id}-prompt-connection`;
  const chosen = connections.find((c) => c.id === connectionId);
  const missing = connectionId !== "" && !chosen;

  return (
    <section className="flex flex-col gap-3">
      <h3 className="text-sm font-medium">Model connection</h3>
      <Labeled id={id} label="Connection" issue={fieldIssue(issues, node.id, "data.connection_id")}>
        <SelectField
          id={id}
          value={chosen ? chosen.id : ""}
          placeholder="Select a connection…"
          onValueChange={onPick}
          options={promptConnections(connections, connectionId).map((c) => ({
            value: c.id,
            label: `${c.name} (${c.typeName})`,
          }))}
        />
      </Labeled>
      {chosen && !lacksBaseUrl(chosen) && (
        <p className="text-xs text-muted-foreground">
          Calls <code>base URL/chat/completions</code> on {chosen.hosts || "its host"}. The key is added for you and
          never shown.
        </p>
      )}
      {lacksBaseUrl(chosen) && (
        <p role="alert" className="text-xs text-red-700 dark:text-red-400">
          This connection has no base URL, so the run will fail. Pick an OpenAI-compatible connection.
        </p>
      )}
      {missing && (
        <p role="alert" className="text-xs text-red-700 dark:text-red-400">
          The saved connection no longer exists. Pick another, or the run will fail.
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        {connections.length === 0 ? "No connections yet. " : ""}
        Works with OpenAI, Groq, OpenRouter, Ollama and any provider with an OpenAI-style API.{" "}
        <a
          href="/connections"
          target="_blank"
          rel="noreferrer"
          className="underline underline-offset-2 hover:text-foreground"
        >
          Manage connections
        </a>
      </p>
    </section>
  );
}

export function PromptForm({ node }: { node: FlowNode }) {
  const setConfig = useEditor((s) => s.setNodeConfig);
  const issues = useEditor((s) => s.issues);
  const config = node.data.config as PromptData;
  const update: Update = (patch) => setConfig(node.id, { ...config, ...patch });
  const prefix = `${node.id}-prompt`;

  return (
    <>
      <ConnectionField node={node} connectionId={config.connection_id} onPick={(connection_id) => update({ connection_id })} />
      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-medium">Message</h3>
        <Labeled id={`${prefix}-system`} label="System instructions (optional)" issue={fieldIssue(issues, node.id, "data.system")}>
          <ExpandableInput
            id={`${prefix}-system`}
            nodeId={node.id}
            title="System instructions"
            value={config.system}
            placeholder="Answer in one sentence."
            onChange={(system) => update({ system })}
          />
        </Labeled>
        <Labeled id={`${prefix}-prompt`} label="Prompt" issue={fieldIssue(issues, node.id, "data.prompt")}>
          <ExpandableInput
            id={`${prefix}-prompt`}
            nodeId={node.id}
            title="Prompt"
            value={config.prompt}
            placeholder="Summarize: {{ input.text }}"
            onChange={(prompt) => update({ prompt })}
          />
        </Labeled>
        <p className="text-xs text-muted-foreground">
          Both can use <code>{"{{ input.name }}"}</code> and earlier node outputs. Secrets are not allowed here.
        </p>
      </section>
      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-medium">Model</h3>
        <Labeled id={`${prefix}-model`} label="Model (optional)" issue={fieldIssue(issues, node.id, "data.model")}>
          <ExpandableInput
            id={`${prefix}-model`}
            nodeId={node.id}
            title="Model"
            value={config.model}
            placeholder="Empty uses the connection's default model"
            onChange={(model) => update({ model })}
          />
        </Labeled>
        <NumberField
          id={`${prefix}-temperature`}
          label="Temperature (0 to 2)"
          value={config.temperature}
          placeholder="Provider default"
          parse={parseTemperature}
          onValue={(temperature) => update({ temperature })}
        />
        <NumberField
          id={`${prefix}-max-tokens`}
          label="Max tokens"
          value={config.max_tokens}
          placeholder="Provider default"
          parse={parseMaxTokens}
          onValue={(max_tokens) => update({ max_tokens })}
        />
        <NumberField
          id={`${prefix}-timeout`}
          label="Timeout (seconds)"
          value={config.timeout_seconds}
          placeholder="Server default"
          parse={parseTimeout}
          onValue={(timeout_seconds) => update({ timeout_seconds })}
        />
      </section>
      <p className="text-xs text-muted-foreground">
        Later nodes read the reply as <code>nodes.{node.id}.output.text</code>, plus <code>model</code>,{" "}
        <code>finish_reason</code> and <code>usage</code>.
      </p>
    </>
  );
}
