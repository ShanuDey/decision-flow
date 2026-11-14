"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { evaluateExpression } from "@/lib/api/client";
import type { EvaluateResponse } from "@/lib/api/models";
import { call } from "@/lib/call";
import { fromReactFlow } from "@/lib/graph/convert";
import { availableData } from "@/lib/graph/scope";
import { cn } from "@/lib/utils";

import { CodeEditor } from "./code-editor";
import { useEditor } from "./store";
import { TestPane } from "./test-pane";

export type SourceKind = "expression" | "template";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  nodeId: string;
  title: string;
  kind: SourceKind;
  value: string;
  onChange: (value: string) => void;
}

const liveGraph = () => {
  const { nodes, edges, variables } = useEditor.getState();
  return fromReactFlow({ nodes, edges, variables });
};

// Slow enough that typing does not hammer the API; skips text it has already checked.
const CHECK_DELAY_MS = 800;

function useCheck(kind: SourceKind, source: string) {
  const [check, setCheck] = useState<EvaluateResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const lastChecked = useRef("");
  useEffect(() => {
    const key = `${kind}\n${source}`;
    if (!source.trim() || lastChecked.current === key) return;
    let stale = false;
    const timer = setTimeout(async () => {
      const result = await call(evaluateExpression({ kind, source }));
      if (stale) return;
      lastChecked.current = result.ok ? key : "";
      setFailed(!result.ok);
      setCheck(result.ok ? result.data : null);
    }, CHECK_DELAY_MS);
    return () => {
      stale = true;
      clearTimeout(timer);
    };
  }, [kind, source]);
  const has = source.trim() !== "";
  return { check: has ? check : null, failed: has && failed };
}

export default function ExpandDialog({
  open,
  onOpenChange,
  nodeId,
  title,
  kind,
  value,
  onChange,
}: Props) {
  const name = useEditor((s) => s.nodes.find((n) => n.id === nodeId)?.data.name ?? nodeId);
  const sections = useMemo(() => availableData(liveGraph(), nodeId), [nodeId]);
  const [insert, setInsert] = useState<{ text: string; n: number } | null>(null);
  const { check, failed } = useCheck(kind, value);

  const wrap = (path: string) => (kind === "template" ? `{{ ${path} }}` : path);
  const invalid = check !== null && !check.valid;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="flex h-[min(640px,calc(100vh-2rem))] w-[min(1104px,calc(100vw-2rem))] max-w-none flex-col gap-0 overflow-hidden p-0 sm:max-w-none"
      >
        <header className="flex h-14 shrink-0 items-center gap-2.5 border-b px-4">
          <DialogTitle className="text-[15px] font-semibold">
            {name} <span className="text-muted-foreground">›</span> {title}
          </DialogTitle>
          <Badge variant="secondary">Built-in</Badge>
          <DialogDescription className="ml-auto text-xs">Edits apply live</DialogDescription>
          <Button onClick={() => onOpenChange(false)}>Done</Button>
        </header>
        <div className="flex min-h-0 flex-1">
          <aside
            aria-label="Available data"
            className="hidden w-[260px] shrink-0 overflow-y-auto border-r bg-muted/30 md:block"
          >
            <p className="px-4 pt-3 pb-2 text-[11px] font-semibold tracking-wider text-muted-foreground">
              AVAILABLE DATA
            </p>
            {sections.length === 0 && (
              <p className="px-4 text-xs text-muted-foreground">Nothing to reference yet.</p>
            )}
            {sections.map((section) => (
              <div key={section.title} className="pb-2">
                <p className="px-4 py-1 font-mono text-xs font-semibold">{section.title}</p>
                {section.items.map((item) => (
                  <button
                    key={item.path}
                    type="button"
                    onClick={() => setInsert({ text: wrap(item.path), n: (insert?.n ?? 0) + 1 })}
                    className="flex w-full items-baseline justify-between gap-2 px-6 py-1 text-left font-mono text-xs hover:bg-muted"
                  >
                    <span className="truncate">{item.label}</span>
                    <span className="shrink-0 font-sans text-muted-foreground">{item.detail}</span>
                  </button>
                ))}
              </div>
            ))}
            <p className="px-4 py-3 text-xs text-muted-foreground">Click to insert at the cursor.</p>
          </aside>
          <div className="flex min-w-0 flex-1 flex-col">
            <div className="min-h-0 flex-1 py-3">
              <CodeEditor
                value={value}
                onChange={onChange}
                getGraph={liveGraph}
                nodeId={nodeId}
                label={title}
                insertRequest={insert}
              />
            </div>
            <p
              role="status"
              data-testid="check-strip"
              className={cn(
                "shrink-0 border-t px-4 py-1.5 text-xs",
                failed
                  ? "bg-muted text-muted-foreground"
                  : invalid
                    ? "bg-red-50 text-red-800 dark:bg-red-950/40 dark:text-red-300"
                    : "bg-green-50 text-green-800 dark:bg-green-950/40 dark:text-green-300",
              )}
            >
              {failed
                ? "Could not check the expression."
                : !check
                  ? "Checking…"
                  : check.valid
                    ? kind === "template"
                      ? "Valid template"
                      : `Valid expression · returns ${(check.return_type ?? "").toLowerCase()}`
                    : check.error}
            </p>
          </div>
          <aside
            aria-label="Test"
            className="hidden w-[300px] shrink-0 flex-col gap-3 overflow-y-auto border-l p-4 lg:flex"
          >
            <TestPane nodeId={nodeId} kind={kind} source={value} idPrefix="expand" />
          </aside>
        </div>
      </DialogContent>
    </Dialog>
  );
}
