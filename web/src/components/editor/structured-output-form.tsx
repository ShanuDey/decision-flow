"use client";

import { Input } from "@/components/ui/input";
import { SelectField } from "@/components/ui/select-field";
import type { FlowNode } from "@/lib/graph/convert";
import { parseTimeout } from "@/lib/graph/http-request";
import { parseMaxTokens, parseTemperature } from "@/lib/graph/prompt";
import { fieldNameProblem, MODES, STRUCTURED_TYPES } from "@/lib/graph/structured-output";
import type { FieldType, StructuredOutputData } from "@/lib/graph/types";

import { ExpandableInput } from "./expand-field";
import { EnumValues, Labeled, ListEditor, patch, typeChange } from "./fields";
import { fieldIssue } from "./issues";
import { ConnectionField, NumberField } from "./prompt-form";
import { useEditor } from "./store";

type Update = (patch: Partial<StructuredOutputData>) => void;

function FieldsEditor({ node, config, update }: { node: FlowNode; config: StructuredOutputData; update: Update }) {
  const issues = useEditor((s) => s.issues);
  const set = (fields: StructuredOutputData["fields"]) => update({ fields });
  const names = config.fields.map((f) => f.name);

  return (
    <ListEditor
      title="Fields to return"
      items={config.fields}
      addLabel="Add field"
      emptyText="No fields yet. Each field becomes a value later nodes can read."
      onAdd={() => set([...config.fields, { name: "", type: "string" }])}
      onRemove={(i) => set(config.fields.filter((_, j) => j !== i))}
      renderItem={(field, i) => {
        const id = `${node.id}-field-${i}`;
        const problem = fieldNameProblem(names, i);
        return (
          <>
            <Labeled id={`${id}-name`} label="Name" issue={fieldIssue(issues, node.id, `data.fields.${i}`)}>
              <Input
                id={`${id}-name`}
                className="h-10 font-mono text-xs"
                value={field.name}
                placeholder="customer_name"
                autoComplete="off"
                spellCheck={false}
                aria-invalid={problem !== null && field.name !== ""}
                onChange={(e) => set(patch(config.fields, i, { name: e.target.value }))}
              />
              {problem && field.name !== "" && (
                <p role="alert" className="text-xs text-red-700 dark:text-red-400">
                  {problem}
                </p>
              )}
            </Labeled>
            <Labeled id={`${id}-type`} label="Type">
              <SelectField
                id={`${id}-type`}
                value={field.type}
                onValueChange={(t) => set(patch(config.fields, i, typeChange(t as FieldType)))}
                options={STRUCTURED_TYPES}
              />
            </Labeled>
            {field.type === "enum" && (
              <Labeled id={`${id}-values`} label="Allowed values (comma separated)">
                <EnumValues
                  id={`${id}-values`}
                  values={field.values}
                  onChange={(values) => set(patch(config.fields, i, { values }))}
                />
              </Labeled>
            )}
            <Labeled id={`${id}-description`} label="What it is (helps the model)">
              <Input
                id={`${id}-description`}
                className="h-10"
                value={field.description ?? ""}
                placeholder="The customer's full name"
                onChange={(e) => set(patch(config.fields, i, { description: e.target.value }))}
              />
            </Labeled>
          </>
        );
      }}
    />
  );
}

export function StructuredOutputForm({ node }: { node: FlowNode }) {
  const setConfig = useEditor((s) => s.setNodeConfig);
  const issues = useEditor((s) => s.issues);
  const config = node.data.config as StructuredOutputData;
  const update: Update = (patch) => setConfig(node.id, { ...config, ...patch });
  const prefix = `${node.id}-structured`;

  return (
    <>
      <ConnectionField
        node={node}
        connectionId={config.connection_id}
        onPick={(connection_id) => update({ connection_id })}
      />
      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-medium">Message</h3>
        <Labeled id={`${prefix}-system`} label="System instructions (optional)" issue={fieldIssue(issues, node.id, "data.system")}>
          <ExpandableInput
            id={`${prefix}-system`}
            nodeId={node.id}
            title="System instructions"
            value={config.system}
            placeholder="Extract only what the text states."
            onChange={(system) => update({ system })}
          />
        </Labeled>
        <Labeled id={`${prefix}-prompt`} label="Prompt" issue={fieldIssue(issues, node.id, "data.prompt")}>
          <ExpandableInput
            id={`${prefix}-prompt`}
            nodeId={node.id}
            title="Prompt"
            value={config.prompt}
            placeholder="Extract the contact details from: {{ input.text }}"
            onChange={(prompt) => update({ prompt })}
          />
        </Labeled>
        <p className="text-xs text-muted-foreground">
          Both can use <code>{"{{ input.name }}"}</code> and earlier node outputs. Secrets are not allowed here.
        </p>
      </section>
      <FieldsEditor node={node} config={config} update={update} />
      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-medium">Model</h3>
        <Labeled id={`${prefix}-mode`} label="How the structure is asked for">
          <SelectField
            id={`${prefix}-mode`}
            value={config.mode}
            onValueChange={(mode) => update({ mode: mode as StructuredOutputData["mode"] })}
            options={[...MODES]}
          />
        </Labeled>
        <p className="text-xs text-muted-foreground">
          If a provider or model rejects the structure, choose “Ask for a JSON object”. The answer is checked either
          way.
        </p>
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
        Later nodes read each field as <code>nodes.{node.id}.output.&lt;name&gt;</code>. The run fails if the
        answer is not JSON or a field is missing or has the wrong type.
      </p>
    </>
  );
}
