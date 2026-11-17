"use client";

import { useEffect } from "react";

import type { FlowNode } from "@/lib/graph/convert";
import { missingInputs, syncInputs } from "@/lib/graph/subflow";
import type { SubflowData } from "@/lib/graph/types";
import { SelectField } from "@/components/ui/select-field";

import { ExpandableInput } from "./expand-field";
import { FieldError, Labeled } from "./fields";
import { fieldIssue } from "./issues";
import { useEditor } from "./store";
import { ensureContracts } from "./subflows";

export function SubflowForm({ node }: { node: FlowNode }) {
  const setConfig = useEditor((s) => s.setNodeConfig);
  const issues = useEditor((s) => s.issues);
  const flows = useEditor((s) => s.publishedFlows);
  const flowId = useEditor((s) => s.flowId);
  const config = node.data.config as SubflowData;
  const contract = useEditor((s) => s.contracts[config.flow_id]);

  useEffect(() => {
    if (config.flow_id) void ensureContracts([config.flow_id]);
  }, [config.flow_id]);

  async function pick(id: string) {
    setConfig(node.id, { flow_id: id, inputs: {} });
    if (!id) return;
    await ensureContracts([id]);
    const loaded = useEditor.getState().contracts[id];
    if (loaded) setConfig(node.id, { flow_id: id, inputs: syncInputs(loaded, {}) });
  }

  const known = flows.some((f) => f.id === config.flow_id);
  const missing = contract ? missingInputs(contract, config.inputs) : [];

  return (
    <section className="flex flex-col gap-4">
      <h3 className="text-sm font-medium">Flow to run</h3>
      <Labeled
        id={`${node.id}-flow`}
        label="Published flow"
        issue={fieldIssue(issues, node.id, "data.flow_id")}
      >
        <SelectField
          id={`${node.id}-flow`}
          value={config.flow_id}
          placeholder="Select a flow…"
          onValueChange={pick}
          options={[
            ...(config.flow_id && !known
              ? [{ value: config.flow_id, label: "Unavailable flow" }]
              : []),
            ...flows
              .filter((f) => f.id !== flowId)
              .map((f) => ({ value: f.id, label: `${f.name} (v${f.version})` })),
          ]}
        />
      </Labeled>
      <p className="text-xs text-muted-foreground">
        Always runs the flow&apos;s latest published version. Only flows with a published version are
        listed.
      </p>
      {config.flow_id && contract === null && (
        <p role="alert" className="text-xs text-red-700 dark:text-red-400">
          This flow is missing or has no published version.
        </p>
      )}
      {contract && (
        <>
          <h3 className="text-sm font-medium">Inputs</h3>
          {contract.inputs.length === 0 && (
            <p className="text-xs text-muted-foreground">This flow takes no inputs.</p>
          )}
          {contract.inputs.map((input) => {
            const id = `${node.id}-in-${input.name}`;
            const unset = missing.includes(input.name);
            return (
              <Labeled
                key={input.name}
                id={id}
                label={`${input.name} · ${input.type}${(input.required ?? true) && input.default == null ? " · required" : ""}`}
                issue={fieldIssue(issues, node.id, `data.inputs.${input.name}`)}
              >
                <ExpandableInput
                  id={id}
                  nodeId={node.id}
                  title={`Input ${input.name}`}
                  value={config.inputs[input.name] ?? ""}
                  placeholder="{{ input.amount }}"
                  onChange={(value) =>
                    setConfig(node.id, { ...config, inputs: { ...config.inputs, [input.name]: value } })
                  }
                />
                {unset && !fieldIssue(issues, node.id, `data.inputs.${input.name}`) && (
                  <FieldError issue={{ code: "missing_subflow_input", message: "Needs a value", node_id: node.id, field: null }} />
                )}
              </Labeled>
            );
          })}
          <h3 className="text-sm font-medium">Outputs</h3>
          <p className="text-xs text-muted-foreground">
            {contract.outputs.length === 0
              ? "This flow returns nothing."
              : contract.outputs.map((o) => `${o.name} (${o.type})`).join(", ")}
          </p>
          <p className="text-xs text-muted-foreground">
            Later nodes read them as <code>nodes.{node.id}.output.&lt;name&gt;</code>.
          </p>
        </>
      )}
    </section>
  );
}
