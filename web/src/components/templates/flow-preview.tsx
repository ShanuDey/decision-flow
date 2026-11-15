"use client";

import { Background, Handle, type NodeProps, Position, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useTheme } from "next-themes";
import { useMemo } from "react";

import { type FlowNode, parseDraft, toReactFlow } from "@/lib/graph/convert";
import { NODE_ICONS } from "@/lib/graph/node-icons";
import { NODE_SPECS } from "@/lib/graph/nodes";
import type { NodeType } from "@/lib/graph/types";

function PreviewNode({ type, data }: NodeProps<FlowNode>) {
  const spec = NODE_SPECS[type as NodeType];
  const Icon = NODE_ICONS[type as NodeType];
  return (
    <div className="flex items-center gap-2 rounded-lg border bg-card px-3 py-2 text-card-foreground shadow-sm">
      {spec.acceptsIncoming && <Handle type="target" position={Position.Left} isConnectable={false} />}
      <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      <span className="text-sm font-medium whitespace-nowrap">{data.name}</span>
      {spec.handles.length > 0
        ? spec.handles.map((handle, i) => (
            <Handle
              key={handle}
              id={handle}
              type="source"
              position={Position.Right}
              isConnectable={false}
              style={{ top: `${((i + 1) * 100) / (spec.handles.length + 1)}%` }}
            />
          ))
        : spec.acceptsOutgoing && (
            <Handle type="source" position={Position.Right} isConnectable={false} />
          )}
    </div>
  );
}

const nodeTypes = {
  start: PreviewNode,
  assign: PreviewNode,
  condition: PreviewNode,
  end: PreviewNode,
};

export function FlowPreview({ draft }: { draft: unknown }) {
  const { resolvedTheme } = useTheme();
  const graph = useMemo(() => {
    const parsed = parseDraft(draft);
    return parsed ? toReactFlow(parsed) : null;
  }, [draft]);

  if (!graph) {
    return <p className="p-4 text-sm text-muted-foreground">No preview available.</p>;
  }
  return (
    <ReactFlow
      nodes={graph.nodes}
      edges={graph.edges}
      nodeTypes={nodeTypes}
      colorMode={resolvedTheme === "dark" ? "dark" : "light"}
      fitView
      fitViewOptions={{ padding: 0.15 }}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      panOnDrag={false}
      zoomOnScroll={false}
      zoomOnPinch={false}
      zoomOnDoubleClick={false}
      preventScrolling={false}
      proOptions={{ hideAttribution: true }}
    >
      <Background />
    </ReactFlow>
  );
}
