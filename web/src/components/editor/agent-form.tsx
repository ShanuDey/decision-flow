"use client";

import { Input } from "@/components/ui/input";
import { SelectField } from "@/components/ui/select-field";
import { Textarea } from "@/components/ui/textarea";
import { parseIterations, parseMaxSeconds, toolNameProblem } from "@/lib/graph/agent";
import type { FlowNode } from "@/lib/graph/convert";
import { parseTimeout } from "@/lib/graph/http-request";
import { parseMaxTokens, parseTemperature } from "@/lib/graph/prompt";
import type { AgentData, AgentTool } from "@/lib/graph/types";

import { ExpandableInput } from "./expand-field";
import { Labeled, ListEditor, patch } from "./fields";
import { fieldIssue } from "./issues";
import { ConnectionField, NumberField } from "./prompt-form";
import { useEditor } from "./store";
import { ensureContracts } from "./subflows";

type Update = (patch: Partial<AgentData>) => void;

// A starting name the model can use; the flow's name is the only hint available.
function toolName(flowName: string): string {
  return flowName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 64);
}

function ToolsEditor({ node, config, update }: { node: FlowNode; config: AgentData; update: Update }) {
  const issues = useEditor((s) => s.issues);
  const flows = useEditor((s) => s.publishedFlows);
  const more = useEditor((s) => s.publishedFlowsMore);
  const contracts = useEditor((s) => s.contracts);
  const currentFlow = useEditor((s) => s.flowId);
  const set = (tools: AgentTool[]) => update({ tools });
  const names = config.tools.map((t) => t.name);

  async function pick(i: number, flowId: string) {
    const tool = config.tools[i];
    const flow = flows.find((f) => f.id === flowId);
    set(patch(config.tools, i, { flow_id: flowId, name: tool.name || (flow ? toolName(flow.name) : "") }));
    if (flowId) await ensureContracts([flowId]);
  }

  return (
    <ListEditor
      title="Tools (flows the model can run)"
      items={config.tools}
      addLabel="Add tool"
      emptyText="No tools yet. Without tools the agent can only answer from the prompt."
      onAdd={() => set([...config.tools, { flow_id: "", name: "", description: "" }])}
      onRemove={(i) => set(config.tools.filter((_, j) => j !== i))}
      renderItem={(tool, i) => {
        const id = `${node.id}-tool-${i}`;
        const problem = toolNameProblem(names, i);
        const contract = contracts[tool.flow_id];
        const known = flows.some((f) => f.id === tool.flow_id);
        return (
          <>
            <Labeled id={`${id}-flow`} label="Published flow" issue={fieldIssue(issues, node.id, `data.tools.${i}.flow_id`)}>
              <SelectField
                id={`${id}-flow`}
                value={tool.flow_id}
                placeholder="Select a flow…"
                onValueChange={(flowId) => void pick(i, flowId)}
                options={[
                  ...(tool.flow_id && !known ? [{ value: tool.flow_id, label: "Unavailable flow" }] : []),
                  ...flows
                    .filter((f) => f.id !== currentFlow)
                    .map((f) => ({ value: f.id, label: `${f.name} (v${f.version})` })),
                ]}
              />
              {more && (
                <p className="text-xs text-muted-foreground">
                  Only the first flows by name are listed. Rename or publish to reach others.
                </p>
              )}
            </Labeled>
            <Labeled id={`${id}-name`} label="Tool name" issue={fieldIssue(issues, node.id, `data.tools.${i}.name`)}>
              <Input
                id={`${id}-name`}
                className="h-10 font-mono text-xs"
                value={tool.name}
                placeholder="lookup_order"
                autoComplete="off"
                spellCheck={false}
                aria-invalid={problem !== null && tool.name !== ""}
                onChange={(e) => set(patch(config.tools, i, { name: e.target.value }))}
              />
              {problem && tool.name !== "" && (
                <p role="alert" className="text-xs text-red-700 dark:text-red-400">
                  {problem}
                </p>
              )}
            </Labeled>
            <Labeled
              id={`${id}-description`}
              label="What it does and when to use it"
              issue={fieldIssue(issues, node.id, `data.tools.${i}.description`)}
            >
              <Textarea
                id={`${id}-description`}
                rows={3}
                value={tool.description}
                placeholder="Returns the status and ship date of an order. Needs the order id."
                onChange={(e) => set(patch(config.tools, i, { description: e.target.value }))}
              />
            </Labeled>
            {contract && (
              <p className="text-xs text-muted-foreground">
                The model fills in {contract.inputs.length === 0 ? "nothing" : contract.inputs.map((f) => f.name).join(", ")}
                {" "}and gets back {contract.outputs.length === 0 ? "nothing" : contract.outputs.map((o) => o.name).join(", ")}.
              </p>
            )}
            {tool.flow_id && contract === null && (
              <p role="alert" className="text-xs text-red-700 dark:text-red-400">
                This flow is missing or has no published version.
              </p>
            )}
          </>
        );
      }}
    />
  );
}

export function AgentForm({ node }: { node: FlowNode }) {
  const setConfig = useEditor((s) => s.setNodeConfig);
  const issues = useEditor((s) => s.issues);
  const config = node.data.config as AgentData;
  const update: Update = (change) => setConfig(node.id, { ...config, ...change });
  const prefix = `${node.id}-agent`;

  return (
    <>
      <ConnectionField node={node} connectionId={config.connection_id} onPick={(connection_id) => update({ connection_id })} />
      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-medium">Task</h3>
        <Labeled id={`${prefix}-instructions`} label="Instructions (optional)" issue={fieldIssue(issues, node.id, "data.instructions")}>
          <ExpandableInput
            id={`${prefix}-instructions`}
            nodeId={node.id}
            title="Instructions"
            value={config.instructions}
            placeholder="You help support staff. Use the tools before you answer."
            onChange={(instructions) => update({ instructions })}
          />
        </Labeled>
        <Labeled id={`${prefix}-prompt`} label="Task" issue={fieldIssue(issues, node.id, "data.prompt")}>
          <ExpandableInput
            id={`${prefix}-prompt`}
            nodeId={node.id}
            title="Task"
            value={config.prompt}
            placeholder="Find the status of order {{ input.order_id }}"
            onChange={(prompt) => update({ prompt })}
          />
        </Labeled>
        <p className="text-xs text-muted-foreground">
          Both can use <code>{"{{ input.name }}"}</code> and earlier node outputs. Secrets are not allowed here.
        </p>
      </section>
      <ToolsEditor node={node} config={config} update={update} />
      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-medium">Limits</h3>
        <NumberField
          id={`${prefix}-iterations`}
          label="Max iterations (model calls)"
          value={config.max_iterations}
          placeholder="8"
          parse={parseIterations}
          onValue={(value) => value !== null && update({ max_iterations: value })}
        />
        <NumberField
          id={`${prefix}-total-tokens`}
          label="Max total tokens"
          value={config.max_total_tokens}
          placeholder="No limit"
          parse={parseMaxTokens}
          onValue={(max_total_tokens) => update({ max_total_tokens })}
        />
        <NumberField
          id={`${prefix}-seconds`}
          label="Max seconds for the whole agent"
          value={config.max_seconds}
          placeholder="120"
          parse={parseMaxSeconds}
          onValue={(max_seconds) => update({ max_seconds })}
        />
        <p className="text-xs text-muted-foreground">
          The node fails if a limit is reached before the agent answers. Flows it already ran are not undone.
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
          label="Max tokens per model call"
          value={config.max_tokens}
          placeholder="Provider default"
          parse={parseMaxTokens}
          onValue={(max_tokens) => update({ max_tokens })}
        />
        <NumberField
          id={`${prefix}-timeout`}
          label="Timeout per model call (seconds)"
          value={config.timeout_seconds}
          placeholder="Server default"
          parse={parseTimeout}
          onValue={(timeout_seconds) => update({ timeout_seconds })}
        />
      </section>
      <p className="text-xs text-muted-foreground">
        Later nodes read the answer as <code>nodes.{node.id}.output.text</code>, plus <code>steps</code>,{" "}
        <code>iterations</code>, <code>usage</code> and <code>model</code>.
      </p>
    </>
  );
}
