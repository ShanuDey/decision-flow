"use client";

import { Handle, type NodeProps, Position } from "@xyflow/react";
import { CircleAlert, Flag, type LucideIcon, Play, Variable } from "lucide-react";

import type { FlowNode } from "@/lib/graph/convert";
import { NODE_SPECS } from "@/lib/graph/nodes";
import type { NodeType } from "@/lib/graph/types";
import { cn } from "@/lib/utils";

import { issuesForNode } from "./issues";
import { useEditor } from "./store";

export const NODE_ICONS: Record<NodeType, LucideIcon> = {
  start: Play,
  assign: Variable,
  end: Flag,
};

function summary(node: FlowNode): string {
  const config = node.data.config;
  const count = (n: number, noun: string) => `${n} ${noun}${n === 1 ? "" : "s"}`;
  if ("inputs" in config) return count(config.inputs.length, "input");
  if ("outputs" in config) return count(config.outputs.length, "output");
  return count(config.assignments.length, "assignment");
}

export function NodeView({ id, type, data, selected }: NodeProps<FlowNode>) {
  const nodeType = type as NodeType;
  const spec = NODE_SPECS[nodeType];
  const Icon = NODE_ICONS[nodeType];
  const problems = useEditor((s) => issuesForNode(s.issues, id).length);
  const node = { data } as FlowNode;

  return (
    <div
      className={cn(
        "w-52 rounded-xl border bg-card px-3 py-2.5 text-card-foreground shadow-sm",
        selected && "ring-2 ring-ring",
        problems > 0 && "border-red-600 dark:border-red-400",
      )}
    >
      {spec.acceptsIncoming && <Handle type="target" position={Position.Left} />}
      <div className="flex items-center gap-2">
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
      <p className="mt-1 text-xs text-muted-foreground">{summary(node)}</p>
      {spec.acceptsOutgoing && <Handle type="source" position={Position.Right} />}
    </div>
  );
}

export const nodeTypes = { start: NodeView, assign: NodeView, end: NodeView };
