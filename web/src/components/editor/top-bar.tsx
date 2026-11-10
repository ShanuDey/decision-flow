"use client";

import { ArrowLeft, CircleCheck, CircleDot, ListChecks, Save } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { type RunOutcome, save, validate } from "./actions";
import { useEditor } from "./store";
import { TestDialog } from "./test-dialog";

export function TopBar({ onOutcome }: { onOutcome: (outcome: RunOutcome) => void }) {
  const name = useEditor((s) => s.name);
  const dirty = useEditor((s) => s.dirty);
  const savedAt = useEditor((s) => s.savedAt);
  const [busy, setBusy] = useState<"save" | "validate" | null>(null);

  async function run(kind: "save" | "validate") {
    setBusy(kind);
    await (kind === "save" ? save() : validate());
    setBusy(null);
  }

  return (
    <header className="flex min-h-14 flex-wrap items-center gap-3 border-b bg-background px-4 py-2">
      <Link
        href="/flows"
        aria-label="Back to flows"
        onClick={(e) => {
          if (dirty && !window.confirm("You have unsaved changes. Leave without saving?")) {
            e.preventDefault();
          }
        }}
        className="flex size-10 items-center justify-center rounded-lg hover:bg-muted"
      >
        <ArrowLeft className="size-4" aria-hidden />
      </Link>
      <h1 className="min-w-0 truncate text-base font-semibold">{name}</h1>
      <Badge variant="secondary">Draft</Badge>
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground" role="status">
        {dirty ? (
          <>
            <CircleDot className="size-3.5" aria-hidden /> Unsaved changes
          </>
        ) : (
          <>
            <CircleCheck className="size-3.5" aria-hidden />
            {savedAt ? `Saved ${savedAt.toLocaleTimeString([], { timeStyle: "short" })}` : "Up to date"}
          </>
        )}
      </p>
      <div className="ml-auto flex flex-wrap items-center gap-2">
        <Button variant="outline" className="h-10" disabled={busy !== null} onClick={() => run("validate")}>
          <ListChecks aria-hidden /> {busy === "validate" ? "Validating…" : "Validate"}
        </Button>
        <TestDialog onOutcome={onOutcome} />
        <Button className="h-10" disabled={busy !== null || !dirty} onClick={() => run("save")}>
          <Save aria-hidden /> {busy === "save" ? "Saving…" : "Save draft"}
        </Button>
      </div>
    </header>
  );
}
