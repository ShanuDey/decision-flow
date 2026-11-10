"use client";

import { useReactFlow } from "@xyflow/react";
import { Copy, Maximize, PenLine, Plus, Settings2, Trash2 } from "lucide-react";

import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuGroup,
  ContextMenuItem,
  ContextMenuLabel,
  ContextMenuSeparator,
  ContextMenuShortcut,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import { canAdd, NODE_SPECS, NODE_TYPES } from "@/lib/graph/nodes";
import type { NodeType, Position } from "@/lib/graph/types";

import { configureNode, deleteFromCanvas } from "./actions";
import { removableIds, useEditor } from "./store";

export type MenuTarget =
  | { kind: "node"; id: string }
  | { kind: "edge"; id: string }
  | { kind: "pane"; position: Position };

function NodeItems({ id }: { id: string }) {
  const nodes = useEditor((s) => s.nodes);
  const duplicateNode = useEditor((s) => s.duplicateNode);
  const node = nodes.find((n) => n.id === id);
  if (!node) return null;
  const type = node.type as NodeType;
  const refs = nodes.map((n) => ({ id: n.id, name: n.data.name, type: n.type as NodeType }));
  const duplicable = canAdd(type, refs);
  const deletable = removableIds(nodes, [id]).size > 0;

  return (
    <>
      <ContextMenuGroup>
        <ContextMenuLabel>{node.data.name}</ContextMenuLabel>
        <ContextMenuItem onClick={() => configureNode(id)}>
          <Settings2 aria-hidden /> Configure
          <ContextMenuShortcut>Dbl-click</ContextMenuShortcut>
        </ContextMenuItem>
        <ContextMenuItem onClick={() => configureNode(id, { select: true })}>
          <PenLine aria-hidden /> Rename
        </ContextMenuItem>
        <ContextMenuItem disabled={!duplicable} onClick={() => duplicateNode(id)}>
          <Copy aria-hidden /> Duplicate
          {!duplicable && (
            <ContextMenuShortcut>{NODE_SPECS[type].label}: only one</ContextMenuShortcut>
          )}
        </ContextMenuItem>
      </ContextMenuGroup>
      <ContextMenuSeparator />
      <ContextMenuItem
        variant="destructive"
        disabled={!deletable}
        onClick={() => deleteFromCanvas([id], [])}
      >
        <Trash2 aria-hidden /> Delete
        <ContextMenuShortcut>{deletable ? "Del" : "needs one"}</ContextMenuShortcut>
      </ContextMenuItem>
    </>
  );
}

function PaneItems({ position }: { position: Position }) {
  const nodes = useEditor((s) => s.nodes);
  const addNode = useEditor((s) => s.addNode);
  const { fitView } = useReactFlow();
  const refs = nodes.map((n) => ({ id: n.id, name: n.data.name, type: n.type as NodeType }));

  return (
    <>
      <ContextMenuGroup>
        <ContextMenuLabel>Add node here</ContextMenuLabel>
        {NODE_TYPES.map((type) => {
          const allowed = canAdd(type, refs);
          return (
            <ContextMenuItem key={type} disabled={!allowed} onClick={() => addNode(type, position)}>
              <Plus aria-hidden /> {NODE_SPECS[type].label}
              {!allowed && <ContextMenuShortcut>already in the flow</ContextMenuShortcut>}
            </ContextMenuItem>
          );
        })}
      </ContextMenuGroup>
      <ContextMenuSeparator />
      <ContextMenuItem onClick={() => fitView({ padding: 0.3, maxZoom: 1, duration: 200 })}>
        <Maximize aria-hidden /> Fit view
      </ContextMenuItem>
    </>
  );
}

export function CanvasMenu({
  target,
  onReset,
  children,
}: {
  target: MenuTarget | null;
  // Runs first on every right-click, before React Flow reports the target.
  onReset: () => void;
  children: React.ReactNode;
}) {
  return (
    <ContextMenu>
      <ContextMenuTrigger className="h-full min-w-0 flex-1" onContextMenuCapture={onReset}>
        {children}
      </ContextMenuTrigger>
      <ContextMenuContent>
        {target?.kind === "node" && <NodeItems id={target.id} />}
        {target?.kind === "edge" && (
          <ContextMenuItem variant="destructive" onClick={() => deleteFromCanvas([], [target.id])}>
            <Trash2 aria-hidden /> Delete connection
            <ContextMenuShortcut>Del</ContextMenuShortcut>
          </ContextMenuItem>
        )}
        {target?.kind === "pane" && <PaneItems position={target.position} />}
        {target === null && <ContextMenuItem disabled>No actions here</ContextMenuItem>}
      </ContextMenuContent>
    </ContextMenu>
  );
}
