"use client";

import { Plus } from "lucide-react";

import { canAdd, NODE_SPECS, NODE_TYPES } from "@/lib/graph/nodes";
import type { NodeType } from "@/lib/graph/types";

import { NODE_ICONS } from "./node-view";
import { useEditor } from "./store";

export function Palette() {
  const nodes = useEditor((s) => s.nodes);
  const addNode = useEditor((s) => s.addNode);
  const refs = nodes.map((n) => ({ id: n.id, name: n.data.name, type: n.type as NodeType }));

  return (
    <aside className="hidden w-[220px] shrink-0 flex-col gap-2 border-r bg-muted/30 p-3 lg:flex">
      <h2 className="px-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Nodes
      </h2>
      {NODE_TYPES.map((type) => {
        const spec = NODE_SPECS[type];
        const Icon = NODE_ICONS[type];
        const allowed = canAdd(type, refs);
        return (
          <button
            key={type}
            type="button"
            disabled={!allowed}
            onClick={() => addNode(type)}
            className="flex min-h-11 items-center gap-2.5 rounded-lg border bg-background px-3 py-2 text-left text-sm hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="font-medium">{spec.label}</span>
              <span className="truncate text-xs text-muted-foreground">
                {allowed ? spec.description : "Already in the flow"}
              </span>
            </span>
            {allowed && <Plus className="size-4 text-muted-foreground" aria-hidden />}
            <span className="sr-only">Add {spec.label} node</span>
          </button>
        );
      })}
      <p className="mt-2 px-1 text-xs text-muted-foreground">More node types are coming.</p>
    </aside>
  );
}
