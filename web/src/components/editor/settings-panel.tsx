"use client";

import { PanelRightClose, PanelRightOpen, Trash2 } from "lucide-react";
import { useEffect, useSyncExternalStore } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SelectField } from "@/components/ui/select-field";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { FlowNode } from "@/lib/graph/convert";
import { NODE_SPECS } from "@/lib/graph/nodes";
import { ioSummary } from "@/lib/graph/picker";
import type {
  AssignData,
  NodeType,
  ConditionData,
  EndData,
  FieldDef,
  FieldType,
  OutputDef,
  StartData,
  Variable,
} from "@/lib/graph/types";
import { cn } from "@/lib/utils";

import { deleteFromCanvas } from "./actions";
import { ExpandableInput } from "./expand-field";
import { ExpressionInput } from "./expression-input";
import { EnumValues, FieldError, Labeled, ListEditor, TypedValueInput, TypeSelect } from "./fields";
import { fieldIssue, flowIssues, issuesForNode } from "./issues";
import { clampWidth, useLayout } from "./layout";
import { NODE_ICONS } from "./node-view";
import { ResizeHandle } from "./resize-handle";
import { selectedNode, useEditor } from "./store";
import { TestPane } from "./test-pane";

function patch<T>(list: T[], index: number, change: Partial<T>): T[] {
  return list.map((item, i) => (i === index ? { ...item, ...change } : item));
}

// Switching away from enum drops its values; switching type clears a now-meaningless default.
function typeChange(type: FieldType): { type: FieldType; values?: string[] } {
  return type === "enum" ? { type } : { type, values: undefined };
}

function StartForm({ node }: { node: FlowNode }) {
  const setConfig = useEditor((s) => s.setNodeConfig);
  const issues = useEditor((s) => s.issues);
  const config = node.data.config as StartData;
  const set = (inputs: FieldDef[]) => setConfig(node.id, { inputs });

  return (
    <ListEditor
      title="Inputs"
      items={config.inputs}
      addLabel="Add input"
      emptyText="No inputs yet. Callers send these when running the flow."
      onAdd={() => set([...config.inputs, { name: "", type: "string", required: true }])}
      onRemove={(i) => set(config.inputs.filter((_, j) => j !== i))}
      renderItem={(input, i) => {
        const id = `${node.id}-in-${i}`;
        return (
          <>
            <Labeled id={`${id}-name`} label="Name" issue={fieldIssue(issues, node.id, `data.inputs.${i}.name`)}>
              <Input
                id={`${id}-name`}
                className="h-10"
                value={input.name}
                onChange={(e) => set(patch(config.inputs, i, { name: e.target.value }))}
              />
            </Labeled>
            <Labeled id={`${id}-type`} label="Type" issue={fieldIssue(issues, node.id, `data.inputs.${i}.values`)}>
              <TypeSelect
                id={`${id}-type`}
                value={input.type}
                onChange={(t) => set(patch(config.inputs, i, { ...typeChange(t), default: undefined }))}
              />
            </Labeled>
            {input.type === "enum" && (
              <Labeled id={`${id}-values`} label="Allowed values (comma separated)">
                <EnumValues
                  id={`${id}-values`}
                  values={input.values}
                  onChange={(values) => set(patch(config.inputs, i, { values }))}
                />
              </Labeled>
            )}
            <label className="flex min-h-8 items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="size-4"
                checked={input.required ?? true}
                onChange={(e) => set(patch(config.inputs, i, { required: e.target.checked }))}
              />
              Required
            </label>
            {!(input.required ?? true) && (
              <Labeled id={`${id}-default`} label="Default value">
                <TypedValueInput
                  id={`${id}-default`}
                  type={input.type}
                  values={input.values}
                  value={input.default}
                  onChange={(value) => set(patch(config.inputs, i, { default: value }))}
                />
              </Labeled>
            )}
          </>
        );
      }}
    />
  );
}

function EndForm({ node }: { node: FlowNode }) {
  const setConfig = useEditor((s) => s.setNodeConfig);
  const issues = useEditor((s) => s.issues);
  const config = node.data.config as EndData;
  const set = (outputs: OutputDef[]) => setConfig(node.id, { outputs });

  return (
    <ListEditor
      title="Outputs"
      items={config.outputs}
      addLabel="Add output"
      emptyText="No outputs yet. These are returned to the caller."
      onAdd={() => set([...config.outputs, { name: "", type: "string", value: "" }])}
      onRemove={(i) => set(config.outputs.filter((_, j) => j !== i))}
      renderItem={(output, i) => {
        const id = `${node.id}-out-${i}`;
        const valueIssue =
          fieldIssue(issues, node.id, `data.outputs.${i}.value`) ??
          fieldIssue(issues, node.id, `data.outputs.${output.name}.value`);
        return (
          <>
            <Labeled id={`${id}-name`} label="Name" issue={fieldIssue(issues, node.id, `data.outputs.${i}.name`)}>
              <Input
                id={`${id}-name`}
                className="h-10"
                value={output.name}
                onChange={(e) => set(patch(config.outputs, i, { name: e.target.value }))}
              />
            </Labeled>
            <Labeled id={`${id}-type`} label="Type">
              <TypeSelect
                id={`${id}-type`}
                value={output.type}
                onChange={(t) => set(patch(config.outputs, i, typeChange(t)))}
              />
            </Labeled>
            {output.type === "enum" && (
              <Labeled id={`${id}-values`} label="Allowed values (comma separated)">
                <EnumValues
                  id={`${id}-values`}
                  values={output.values}
                  onChange={(values) => set(patch(config.outputs, i, { values }))}
                />
              </Labeled>
            )}
            <Labeled id={`${id}-value`} label="Value" issue={valueIssue}>
              <ExpandableInput
                id={`${id}-value`}
                nodeId={node.id}
                title={`Output ${output.name || i + 1} value`}
                value={output.value}
                placeholder="{{ vars.total }}"
                onChange={(value) => set(patch(config.outputs, i, { value }))}
              />
            </Labeled>
          </>
        );
      }}
    />
  );
}

function ConditionForm({ node }: { node: FlowNode }) {
  const setConfig = useEditor((s) => s.setNodeConfig);
  const issues = useEditor((s) => s.issues);
  const config = node.data.config as ConditionData;

  return (
    <section className="space-y-3">
      <h3 className="text-sm font-medium">Condition</h3>
      <Labeled
        id={`${node.id}-expression`}
        label="Expression (true or false)"
        issue={fieldIssue(issues, node.id, "data.expression")}
      >
        <ExpressionInput
          id={`${node.id}-expression`}
          nodeId={node.id}
          title="Expression"
          value={config.expression}
          placeholder="input.amount > 1000"
          onChange={(expression) => setConfig(node.id, { expression })}
        />
      </Labeled>
      <p className="text-xs text-muted-foreground">
        Type <code>input.</code>, <code>vars.</code> or <code>nodes.</code> for suggestions (Ctrl+Space
        opens them). Only nodes that run before this one are offered.
      </p>
    </section>
  );
}

function AssignForm({ node }: { node: FlowNode }) {
  const setConfig = useEditor((s) => s.setNodeConfig);
  const variables = useEditor((s) => s.variables);
  const issues = useEditor((s) => s.issues);
  const config = node.data.config as AssignData;
  const set = (assignments: AssignData["assignments"]) => setConfig(node.id, { assignments });

  return (
    <ListEditor
      title="Assignments"
      items={config.assignments}
      addLabel="Add assignment"
      emptyText="No assignments yet. Declare variables below first."
      onAdd={() => set([...config.assignments, { variable: variables[0]?.name ?? "", value: "" }])}
      onRemove={(i) => set(config.assignments.filter((_, j) => j !== i))}
      renderItem={(assignment, i) => {
        const id = `${node.id}-as-${i}`;
        const known = variables.some((v) => v.name === assignment.variable);
        return (
          <>
            <Labeled
              id={`${id}-var`}
              label="Variable"
              issue={fieldIssue(issues, node.id, `data.assignments.${i}.variable`)}
            >
              <SelectField
                id={`${id}-var`}
                value={assignment.variable}
                placeholder="Select a variable…"
                onValueChange={(v) => set(patch(config.assignments, i, { variable: v }))}
                options={[
                  ...(!known && assignment.variable
                    ? [{ value: assignment.variable, label: `${assignment.variable} (undeclared)` }]
                    : []),
                  ...variables.map((v) => ({ value: v.name, label: v.name })),
                ]}
              />
            </Labeled>
            <Labeled
              id={`${id}-value`}
              label="Value"
              issue={fieldIssue(issues, node.id, `data.assignments.${i}.value`)}
            >
              <ExpandableInput
                id={`${id}-value`}
                nodeId={node.id}
                title={`Assignment ${i + 1} value`}
                value={assignment.value}
                placeholder="{{ input.amount }}"
                onChange={(value) => set(patch(config.assignments, i, { value }))}
              />
            </Labeled>
          </>
        );
      }}
    />
  );
}

function VariablesForm() {
  const variables = useEditor((s) => s.variables);
  const setVariables = useEditor((s) => s.setVariables);

  return (
    <ListEditor
      title="Flow variables"
      items={variables}
      addLabel="Add variable"
      emptyText="Variables hold values between nodes. Assign nodes write to them."
      onAdd={() => setVariables([...variables, { name: "", type: "string" }])}
      onRemove={(i) => setVariables(variables.filter((_, j) => j !== i))}
      renderItem={(variable: Variable, i) => {
        const id = `var-${i}`;
        return (
          <>
            <Labeled id={`${id}-name`} label="Name">
              <Input
                id={`${id}-name`}
                className="h-10"
                value={variable.name}
                onChange={(e) => setVariables(patch(variables, i, { name: e.target.value }))}
              />
            </Labeled>
            <Labeled id={`${id}-type`} label="Type">
              <TypeSelect
                id={`${id}-type`}
                value={variable.type}
                onChange={(t) =>
                  setVariables(patch(variables, i, { ...typeChange(t), initial: undefined }))
                }
              />
            </Labeled>
            {variable.type === "enum" && (
              <Labeled id={`${id}-values`} label="Allowed values (comma separated)">
                <EnumValues
                  id={`${id}-values`}
                  values={variable.values}
                  onChange={(values) => setVariables(patch(variables, i, { values }))}
                />
              </Labeled>
            )}
            <Labeled id={`${id}-initial`} label="Initial value">
              <TypedValueInput
                id={`${id}-initial`}
                type={variable.type}
                values={variable.values}
                value={variable.initial}
                onChange={(initial) => setVariables(patch(variables, i, { initial }))}
              />
            </Labeled>
          </>
        );
      }}
    />
  );
}

function NodeTitle({ node }: { node: FlowNode }) {
  const type = node.type as NodeType;
  const Icon = NODE_ICONS[type];
  return (
    <>
      <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      <h2 className="min-w-0 truncate text-sm font-semibold">{node.data.name}</h2>
      <Badge variant="secondary">
        {NODE_SPECS[type].source === "builtin" ? "Built-in" : "Community"}
      </Badge>
    </>
  );
}

function NodeDocs({ node }: { node: FlowNode }) {
  const spec = NODE_SPECS[node.type as NodeType];
  const io = ioSummary(node.type as NodeType);
  return (
    <div className="flex flex-col gap-3 text-sm">
      <h3 className="font-semibold">{spec.label}</h3>
      <p className="text-muted-foreground">{spec.description}</p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
        <dt className="text-muted-foreground">Group</dt>
        <dd>{spec.group}</dd>
        <dt className="text-muted-foreground">Inputs</dt>
        <dd>{io.inputs}</dd>
        <dt className="text-muted-foreground">Outputs</dt>
        <dd>{io.outputs}</dd>
      </dl>
    </div>
  );
}

const subscribeResize = (notify: () => void) => {
  window.addEventListener("resize", notify);
  return () => window.removeEventListener("resize", notify);
};

function useViewportWidth(): number {
  return useSyncExternalStore(subscribeResize, () => window.innerWidth, () => 1280);
}

export function SettingsPanel() {
  const node = useEditor(selectedNode);
  const renameNode = useEditor((s) => s.renameNode);
  const issues = useEditor((s) => s.issues);
  const general = flowIssues(issues);
  const storedWidth = useLayout((s) => s.width);
  const collapsed = useLayout((s) => s.collapsed);
  const toggleCollapsed = useLayout((s) => s.toggleCollapsed);
  const focusRequest = useLayout((s) => s.focusRequest);
  const viewport = useViewportWidth();
  // Re-clamped on every render so a smaller window never leaves the panel wider than allowed.
  const width = clampWidth(storedWidth, viewport);

  // Runs after the commit that expanded the panel and rendered the selected node's form.
  useEffect(() => {
    if (!focusRequest) return;
    const input = document.getElementById("node-name") as HTMLInputElement | null;
    if (!input) return;
    input.focus();
    input.scrollIntoView({ block: "nearest" });
    if (focusRequest.select) input.select();
  }, [focusRequest]);

  return (
    <>
      {collapsed && (
        <div className="hidden w-10 shrink-0 flex-col items-center border-l bg-background py-2 lg:flex">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={toggleCollapsed}
            aria-label="Show settings"
            title="Show settings"
          >
            <PanelRightOpen aria-hidden />
          </Button>
        </div>
      )}
      <div
        className={cn("relative h-full w-full shrink-0 lg:w-[var(--panel-width)]", collapsed && "lg:hidden")}
        style={{ "--panel-width": `${width}px` } as React.CSSProperties}
      >
        <ResizeHandle width={width} viewport={viewport} />
        <aside aria-label="Settings" className="flex h-full flex-col border-l bg-background">
          <div className="flex items-center gap-2.5 px-4 pt-3.5">
            {node ? <NodeTitle node={node} /> : <h2 className="text-sm font-semibold">Settings</h2>}
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              className="ml-auto hidden lg:inline-flex"
              onClick={toggleCollapsed}
              aria-label="Hide settings"
              title="Hide settings"
            >
              <PanelRightClose aria-hidden />
            </Button>
          </div>

          {node ? (
            <Tabs key={node.id} defaultValue="settings" className="mt-1.5 min-h-0 flex-1 gap-0">
              <TabsList variant="line" className="w-full justify-start gap-4 border-b px-4">
                <TabsTrigger value="settings" className="flex-none px-1">
                  Settings
                </TabsTrigger>
                <TabsTrigger value="test" className="flex-none px-1">
                  Test
                </TabsTrigger>
                <TabsTrigger value="docs" className="flex-none px-1">
                  Docs
                </TabsTrigger>
              </TabsList>
              <TabsContent value="settings" className="flex flex-col gap-5 overflow-y-auto p-4">
                {general.length > 0 && (
                  <div className="flex flex-col gap-1.5">
                    {general.map((issue, i) => (
                      <FieldError key={i} issue={issue} />
                    ))}
                  </div>
                )}
                <section className="flex flex-col gap-3">
                  <Labeled id="node-name" label="Name" issue={fieldIssue(issues, node.id, "name")}>
                    <Input
                      id="node-name"
                      className="h-10"
                      value={node.data.name}
                      onChange={(e) => renameNode(node.id, e.target.value)}
                    />
                  </Labeled>
                  <p className="text-xs text-muted-foreground">
                    Id: <code>{node.id}</code> (never changes)
                  </p>
                  {issuesForNode(issues, node.id)
                    .filter((i) => !i.field)
                    .map((issue, i) => (
                      <FieldError key={i} issue={issue} />
                    ))}
                </section>
                {node.type === "start" && <StartForm node={node} />}
                {node.type === "end" && <EndForm node={node} />}
                {node.type === "assign" && <AssignForm node={node} />}
                {node.type === "condition" && <ConditionForm node={node} />}
                <VariablesForm />
              </TabsContent>
              <TabsContent value="test" className="overflow-y-auto p-4">
                {node.type === "condition" ? (
                  <TestPane
                    nodeId={node.id}
                    kind="expression"
                    source={(node.data.config as ConditionData).expression}
                    idPrefix="panel"
                  />
                ) : (
                  <p className="text-sm text-muted-foreground">
                    This node has nothing to test on its own. Use Run in the top bar to test the
                    whole flow.
                  </p>
                )}
              </TabsContent>
              <TabsContent value="docs" className="overflow-y-auto p-4">
                <NodeDocs node={node} />
              </TabsContent>
            </Tabs>
          ) : (
            <div className="flex flex-1 flex-col gap-5 overflow-y-auto p-4">
              {general.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  {general.map((issue, i) => (
                    <FieldError key={i} issue={issue} />
                  ))}
                </div>
              )}
              <p className="text-sm text-muted-foreground">Select a node to edit its settings.</p>
              <VariablesForm />
            </div>
          )}

          {node && (
            <div className="border-t px-4 py-3">
              <Button
                type="button"
                variant="ghost"
                className="-ml-2 text-red-700 hover:text-red-700 dark:text-red-400"
                onClick={() => deleteFromCanvas([node.id], [])}
              >
                <Trash2 aria-hidden /> Delete node
              </Button>
            </div>
          )}
        </aside>
      </div>
    </>
  );
}
