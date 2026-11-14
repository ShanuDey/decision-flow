"use client";

import { useState } from "react";

import { Copy, PenLine, Settings2, Trash2 } from "lucide-react";

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
import { canAdd, NODE_SPECS } from "@/lib/graph/nodes";
import type { NodeType } from "@/lib/graph/types";

import { configureNode, deleteFromCanvas } from "./actions";
import { removableIds, useEditor } from "./store";

export type MenuTarget = { kind: "node"; id: string } | { kind: "edge"; id: string };

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
  const [open, setOpen] = useState(false);

  return (
    // Only a node or an edge opens the menu; the empty canvas has no custom actions.
    <ContextMenu open={open && target !== null} onOpenChange={setOpen}>
      <ContextMenuTrigger
        className="h-full min-w-0 flex-1"
        onContextMenuCapture={() => {
          setOpen(false);
          onReset();
        }}
      >
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
      </ContextMenuContent>
    </ContextMenu>
  );
}
