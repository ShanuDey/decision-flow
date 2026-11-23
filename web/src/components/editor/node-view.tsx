"use client";

import { Handle, type NodeProps, Position } from "@xyflow/react";
import { CircleAlert, Plus } from "lucide-react";

import type { FlowNode } from "@/lib/graph/convert";
import { NODE_ICONS } from "@/lib/graph/node-icons";
import { NODE_SPECS } from "@/lib/graph/nodes";
import type { NodeType, SubflowData } from "@/lib/graph/types";
import { cn } from "@/lib/utils";

import { AddNodePicker } from "./add-node-picker";
import { issuesForNode } from "./issues";
import { useEditor } from "./store";

function summary(node: FlowNode, flowName?: string): string {
  const config = node.data.config;
  const count = (n: number, noun: string) => `${n} ${noun}${n === 1 ? "" : "s"}`;
  if ("flow_id" in config) return config.flow_id ? (flowName ?? "Flow not found") : "No flow yet";
  if ("inputs" in config) return count(config.inputs.length, "input");
  if ("outputs" in config) return count(config.outputs.length, "output");
  if ("expression" in config) return config.expression.trim() || "No expression yet";
  if ("url" in config) return config.url.trim() ? `${config.method} ${config.url}` : "No URL yet";
  if ("fields" in config) return config.fields.length > 0 ? count(config.fields.length, "field") : "No fields yet";
  if ("tools" in config) return count(config.tools.length, "tool");
  if ("prompt" in config) return config.prompt.trim() || "No prompt yet";
  return count(config.assignments.length, "assignment");
}

function OutputAdd({ id, handle, top }: { id: string; handle: string | null; top: string }) {
  const connected = useEditor((s) => s.edges.some((e) => e.source === id && e.sourceHandle === handle));
  if (connected) return null;
  return (
    <div className="nodrag nopan absolute -right-11 -translate-y-1/2" style={{ top }}>
      <AddNodePicker
        side="right"
        from={{ id, handle }}
        trigger={
          <button
            type="button"
            aria-label={handle ? `Add node after ${handle}` : "Add next node"}
            className="flex size-6 items-center justify-center rounded-full border-2 border-dashed border-primary bg-background text-primary outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            <Plus className="size-3.5" aria-hidden />
          </button>
        }
      />
    </div>
  );
}

export function NodeView({ id, type, data, selected }: NodeProps<FlowNode>) {
  const nodeType = type as NodeType;
  const spec = NODE_SPECS[nodeType];
  const Icon = NODE_ICONS[nodeType];
  const problems = useEditor((s) => issuesForNode(s.issues, id).length);
  const flowName = useEditor((s) =>
    nodeType === "subflow"
      ? s.publishedFlows.find((f) => f.id === (data.config as SubflowData).flow_id)?.name
      : undefined,
  );
  const node = { data } as FlowNode;
  const text = summary(node, flowName);

  return (
    <div
      className={cn(
        "relative w-52 rounded-xl border bg-card px-3 py-2.5 text-card-foreground shadow-sm",
        selected && "ring-2 ring-ring",
        problems > 0 && "border-red-600 dark:border-red-400",
      )}
    >
      {spec.acceptsIncoming && <Handle type="target" position={Position.Left} />}
      <div className={cn("flex items-center gap-2", spec.handles.length > 0 && "pr-7")}>
        <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
        <span className="truncate text-sm font-medium">{data.name}</span>
        {problems > 0 && (
          <span
            className="ml-auto flex shrink-0 items-center gap-1 text-xs text-red-700 dark:text-red-400"
            title={`${problems} problem${problems === 1 ? "" : "s"}`}
          >
            <CircleAlert className="size-3.5" aria-hidden />
            {problems}
            <span className="sr-only"> problem{problems === 1 ? "" : "s"}</span>
          </span>
        )}
      </div>
      <p
        title={text}
        className={cn("mt-1 truncate text-xs text-muted-foreground", spec.handles.length > 0 && "pr-8")}
      >
        {text}
      </p>
      {spec.handles.length > 0
        ? spec.handles.map((handle, i) => (
            <Handle
              key={handle}
              id={handle}
              type="source"
              position={Position.Right}
              style={{ top: `${((i + 1) * 100) / (spec.handles.length + 1)}%` }}
            />
          ))
        : spec.acceptsOutgoing && <Handle type="source" position={Position.Right} />}
      {spec.handles.length > 0
        ? spec.handles.map((handle, i) => (
            <OutputAdd
              key={handle}
              id={id}
              handle={handle}
              top={`${((i + 1) * 100) / (spec.handles.length + 1)}%`}
            />
          ))
        : spec.acceptsOutgoing && <OutputAdd id={id} handle={null} top="50%" />}
      {spec.handles.map((handle, i) => (
        <span
          key={handle}
          className="pointer-events-none absolute right-3 -translate-y-1/2 text-[10px] text-muted-foreground"
          style={{ top: `${((i + 1) * 100) / (spec.handles.length + 1)}%` }}
        >
          {handle}
        </span>
      ))}
    </div>
  );
}

export const nodeTypes = {
  start: NodeView,
  assign: NodeView,
  condition: NodeView,
  http_request: NodeView,
  prompt: NodeView,
  structured_output: NodeView,
  agent: NodeView,
  subflow: NodeView,
  end: NodeView,
};
