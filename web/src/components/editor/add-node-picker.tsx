"use client";

import { useReactFlow, useStore } from "@xyflow/react";
import { Plus, Search } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { canAdd, canConnect, freeSpot, NODE_SPECS } from "@/lib/graph/nodes";
import { flatTypes, ioSummary, pickerGroups, type SourceFilter } from "@/lib/graph/picker";
import type { NodeType } from "@/lib/graph/types";
import { cn } from "@/lib/utils";

import { NODE_ICONS } from "./node-view";
import { useEditor } from "./store";

const TABS: { value: SourceFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "builtin", label: "Built-in" },
  { value: "community", label: "Community" },
];

const shallowSize = (a: { width: number; height: number }, b: { width: number; height: number }) =>
  a.width === b.width && a.height === b.height;

const SOURCE_LABEL = { builtin: "Built-in", community: "Community" } as const;

interface Props {
  trigger: React.ReactElement;
  // Connects the new node to this node's output.
  from?: { id: string; handle: string | null };
  side?: "bottom" | "right";
  // New nodes land at the center of what the user can see, not off-screen.
  placeAtViewCenter?: boolean;
}

export function AddNodePicker({ trigger, from, side = "bottom", placeAtViewCenter = false }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [source, setSource] = useState<SourceFilter>("all");
  const [active, setActive] = useState<NodeType | null>(null);
  const search = useRef<HTMLInputElement>(null);
  const nodes = useEditor((s) => s.nodes);
  const addNode = useEditor((s) => s.addNode);
  const { getViewport } = useReactFlow();
  const view = useStore((s) => ({ width: s.width, height: s.height }), shallowSize);

  const refs = nodes.map((n) => ({ id: n.id, name: n.data.name, type: n.type as NodeType }));
  const fromType = from ? (nodes.find((n) => n.id === from.id)?.type as NodeType | undefined) : undefined;
  const fits = (t: NodeType) => !fromType || canConnect(fromType, t);
  const available = (t: NodeType) => canAdd(t, refs) && fits(t);
  const reason = (t: NodeType) =>
    !canAdd(t, refs) ? "Already in the flow" : !fits(t) ? "Cannot follow this node" : undefined;
  const groups = pickerGroups(query, source);
  const flat = flatTypes(groups);
  const current =
    active && flat.includes(active)
      ? active
      : (flat.find(available) ?? flat[0] ?? null);

  function add(type: NodeType) {
    if (!available(type)) return;
    if (placeAtViewCenter) {
      const { x, y, zoom } = getViewport();
      const center = { x: (view.width / 2 - x) / zoom, y: (view.height / 2 - y) / zoom };
      addNode(type, freeSpot(center, nodes.map((n) => n.position)), from);
    } else {
      addNode(type, undefined, from);
    }
    setOpen(false);
  }

  function onOpenChange(next: boolean) {
    setOpen(next);
    if (next) {
      setQuery("");
      setSource("all");
      setActive(null);
    }
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (!flat.length || !current) return;
    const i = flat.indexOf(current);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      setActive(flat[(i + (e.key === "ArrowDown" ? 1 : flat.length - 1)) % flat.length]);
    } else if (e.key === "Enter") {
      e.preventDefault();
      add(current);
    }
  }

  const spec = current ? NODE_SPECS[current] : null;
  const io = current ? ioSummary(current) : null;
  const Preview = current ? NODE_ICONS[current] : null;

  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverTrigger render={trigger} />
      <PopoverContent
        side={side}
        className="flex h-[min(520px,var(--available-height))] w-[min(640px,calc(100vw-2rem))] overflow-hidden"
        aria-label="Add node"
      >
        <div className="flex w-[300px] shrink-0 flex-col border-r p-2.5 max-sm:w-full max-sm:border-r-0">
          <div className="flex h-9 items-center gap-2 rounded-lg border border-input px-2.5 focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50">
            <Search className="size-3.5 text-muted-foreground" aria-hidden />
            <input
              ref={search}
              autoFocus
              aria-label="Search nodes"
              placeholder="Search nodes"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onKeyDown}
              className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
          </div>
          <div role="tablist" aria-label="Node source" className="mt-2 flex gap-1">
            {TABS.map((tab) => (
              <button
                key={tab.value}
                type="button"
                role="tab"
                aria-selected={source === tab.value}
                onClick={() => {
                  setSource(tab.value);
                  search.current?.focus();
                }}
                className={cn(
                  "rounded-md px-2.5 py-1 text-xs font-medium text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50",
                  source === tab.value && "bg-muted text-foreground",
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div role="listbox" aria-label="Nodes" className="mt-1 min-h-0 flex-1 overflow-y-auto">
            {groups.length === 0 && (
              <p className="px-2 py-4 text-sm text-muted-foreground">
                {source === "community" && !query
                  ? "No community nodes installed yet."
                  : "No nodes match your search."}
              </p>
            )}
            {groups.map(({ group, types }) => (
              <div key={group} role="group" aria-label={group}>
                <p className="px-2.5 pt-2.5 pb-1 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
                  {group}
                </p>
                {types.map((type) => {
                  const Icon = NODE_ICONS[type];
                  const allowed = available(type);
                  return (
                    <div
                      key={type}
                      title={reason(type)}
                      role="option"
                      aria-selected={current === type}
                      aria-disabled={!allowed}
                      onMouseEnter={() => setActive(type)}
                      onClick={() => add(type)}
                      className={cn(
                        "flex h-9 cursor-pointer items-center gap-2.5 rounded-lg px-2.5 text-sm font-medium",
                        current === type && "bg-muted",
                        !allowed && "cursor-not-allowed opacity-50",
                      )}
                    >
                      <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                      <span className="flex-1 truncate">{NODE_SPECS[type].label}</span>
                      <span className="rounded-full bg-secondary px-1.5 py-0.5 text-[10px] font-semibold text-secondary-foreground">
                        {SOURCE_LABEL[NODE_SPECS[type].source]}
                      </span>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-3 p-6 max-sm:hidden">
          {spec && io && Preview && current ? (
            <>
              <div className="flex items-center gap-2.5">
                <Preview className="size-4 text-muted-foreground" aria-hidden />
                <h3 className="text-base font-semibold">{spec.label}</h3>
                <span className="rounded-full bg-secondary px-1.5 py-0.5 text-[10px] font-semibold text-secondary-foreground">
                  {SOURCE_LABEL[spec.source]}
                </span>
              </div>
              <p className="text-sm leading-relaxed text-muted-foreground">{spec.description}</p>
              <p className="text-xs text-muted-foreground">
                Inputs: {io.inputs} · Outputs: {io.outputs}
              </p>
              <div className="mt-auto flex flex-col gap-2">
                <p className="text-xs text-muted-foreground">Enter to add · Esc to close</p>
                {reason(current) && (
                  <p className="text-xs text-muted-foreground">{reason(current)}.</p>
                )}
                <Button
                  className="w-fit"
                  disabled={!available(current)}
                  onClick={() => add(current)}
                >
                  Add {spec.label}
                </Button>
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">Select a node to see what it does.</p>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

export function AddNodeButton() {
  return (
    <AddNodePicker
      placeAtViewCenter
      trigger={
        <Button className="h-9 shadow-sm">
          <Plus aria-hidden /> Add node
        </Button>
      }
    />
  );
}
