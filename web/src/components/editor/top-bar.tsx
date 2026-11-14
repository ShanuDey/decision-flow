"use client";

import { ArrowLeft, CircleCheck, CircleDot, ListChecks, Play, Save } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useEditorUser } from "@/app/(editor)/editor-user";
import { UserMenu } from "@/app/(app)/user-menu";
import { FlowRenameDialog } from "@/components/flow-rename-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

import { type RunOutcome, save, validate } from "./actions";
import { guardedLeave, useGuardedNavigate } from "./leave-store";
import { useEditor } from "./store";
import { TestDialog } from "./test-dialog";
import { ValidateIssues } from "./validate-popover";

type Busy = "save" | "validate" | "run" | null;

export function TopBar({ onOutcome }: { onOutcome: (outcome: RunOutcome) => void }) {
  const flowId = useEditor((s) => s.flowId);
  const name = useEditor((s) => s.name);
  const setName = useEditor((s) => s.setName);
  const dirty = useEditor((s) => s.dirty);
  const savedAt = useEditor((s) => s.savedAt);
  const problems = useEditor((s) => s.issues.length);
  const user = useEditorUser();
  const navigate = useGuardedNavigate();
  const [busy, setBusy] = useState<Busy>(null);
  const [issuesOpen, setIssuesOpen] = useState(false);
  const [runOpen, setRunOpen] = useState(false);

  async function doSave() {
    setBusy("save");
    await save();
    setBusy(null);
  }

  async function doValidate() {
    setBusy("validate");
    const result = await validate({ quiet: true });
    setBusy(null);
    if (result !== "error") setIssuesOpen(true);
  }

  async function doRun() {
    setBusy("run");
    const result = await validate({ quiet: true });
    setBusy(null);
    if (result === "valid") setRunOpen(true);
    else if (result === "invalid") setIssuesOpen(true);
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "s") return;
      e.preventDefault();
      if (useEditor.getState().dirty) void doSave();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const goBack = (e: React.MouseEvent) => {
    if (!dirty) return;
    e.preventDefault();
    navigate("/flows");
  };

  return (
    <header className="flex min-h-[52px] flex-wrap items-center gap-3 border-b bg-background px-3 py-1.5">
      <Link
        href="/flows"
        aria-label="Back to flows"
        onClick={goBack}
        className="flex size-9 items-center justify-center rounded-lg border hover:bg-muted"
      >
        <ArrowLeft className="size-4" aria-hidden />
      </Link>
      <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-2 text-sm">
        <Link href="/flows" onClick={goBack} className="text-muted-foreground hover:text-foreground">
          Flows
        </Link>
        <span aria-hidden className="text-muted-foreground">
          /
        </span>
        {flowId ? (
          <FlowRenameDialog
            flowId={flowId}
            currentName={name}
            onRenamed={setName}
            trigger={
              <button
                type="button"
                title="Rename flow"
                className="min-w-0 truncate rounded-md px-1 text-base font-semibold outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                {name}
              </button>
            }
          />
        ) : (
          <h1 className="font-semibold">{name}</h1>
        )}
      </nav>
      <Badge variant="secondary" className="hidden sm:inline-flex">
        Draft
      </Badge>
      <p
        className={
          dirty
            ? "flex items-center gap-1.5 text-xs text-amber-800 dark:text-amber-400"
            : "flex items-center gap-1.5 text-xs text-muted-foreground"
        }
        role="status"
      >
        {dirty ? (
          <>
            <CircleDot className="size-3.5" aria-hidden /> Unsaved changes
          </>
        ) : (
          <>
            <CircleCheck className="size-3.5 text-green-700 dark:text-green-400" aria-hidden />
            {savedAt ? `Saved ${savedAt.toLocaleTimeString([], { timeStyle: "short" })}` : "Saved"}
          </>
        )}
      </p>
      <div className="ml-auto flex flex-wrap items-center gap-2">
        <Popover open={issuesOpen} onOpenChange={(open) => !open && setIssuesOpen(false)}>
          <PopoverTrigger
            render={
              <Button
                variant="outline"
                className="h-9"
                disabled={busy !== null}
                onClick={() => void doValidate()}
              />
            }
          >
            <ListChecks aria-hidden /> {busy === "validate" ? "Validating…" : "Validate"}
            {problems > 0 && (
              <span className="rounded-full bg-red-700 px-1.5 text-[11px] text-white">{problems}</span>
            )}
          </PopoverTrigger>
          <PopoverContent align="end" className="w-[360px] max-w-[calc(100vw-1rem)]">
            <ValidateIssues onPick={() => setIssuesOpen(false)} />
          </PopoverContent>
        </Popover>
        <Button
          variant="outline"
          className="h-9"
          disabled={busy !== null || !dirty}
          onClick={() => void doSave()}
        >
          <Save aria-hidden /> {busy === "save" ? "Saving…" : "Save"}
        </Button>
        <Button className="h-9" disabled={busy !== null} onClick={() => void doRun()}>
          <Play aria-hidden /> {busy === "run" ? "Checking…" : "Run"}
        </Button>
        <TestDialog open={runOpen} onOpenChange={setRunOpen} onOutcome={onOutcome} />
        {user && (
          <>
            <div aria-hidden className="mx-1 h-6 w-px bg-border" />
            <UserMenu
              name={user.name}
              email={user.email}
              variant="bar"
              settingsHref={`/settings/appearance?from=/flows/${flowId}`}
              guard={guardedLeave}
            />
          </>
        )}
      </div>
    </header>
  );
}
