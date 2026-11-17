"use client";

import {
  ArrowLeft,
  ChevronDown,
  CircleCheck,
  CircleDot,
  CircleOff,
  Download,
  ListChecks,
  MoreHorizontal,
  Play,
  Variable,
  Rocket,
  Save,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useEditorUser } from "@/app/(editor)/editor-user";
import { UserMenu } from "@/app/(app)/user-menu";
import { FlowRenameDialog } from "@/components/flow-rename-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

import { exportFlow, publish, type RunOutcome, save, validate } from "./actions";
import { guardedLeave, useGuardedNavigate } from "./leave-store";
import { useEditor } from "./store";
import { TestDialog } from "./test-dialog";
import { UnpublishDialog } from "./unpublish-dialog";
import { ValidateIssues } from "./validate-popover";
import { VersionsList } from "./versions-popover";

type Busy = "save" | "validate" | "publish" | "run" | null;

export function TopBar({ onOutcome }: { onOutcome: (outcome: RunOutcome) => void }) {
  const flowId = useEditor((s) => s.flowId);
  const name = useEditor((s) => s.name);
  const setName = useEditor((s) => s.setName);
  const dirty = useEditor((s) => s.dirty);
  const savedAt = useEditor((s) => s.savedAt);
  const problems = useEditor((s) => s.issues.length);
  const variableCount = useEditor((s) => s.variables.length);
  const openVariables = useEditor((s) => s.openVariables);
  const publishedVersion = useEditor((s) => s.publishedVersion);
  // Unsaved edits count: Publish saves first.
  const unpublished = useEditor(
    (s) => s.dirty || s.publishedDraftVersion === null || s.publishedDraftVersion !== s.draftVersion,
  );
  const user = useEditorUser();
  const navigate = useGuardedNavigate();
  const [busy, setBusy] = useState<Busy>(null);
  const [issuesOpen, setIssuesOpen] = useState(false);
  const [runOpen, setRunOpen] = useState(false);
  const [unpublishOpen, setUnpublishOpen] = useState(false);

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

  async function doPublish() {
    setBusy("publish");
    const result = await publish();
    setBusy(null);
    if (result === "invalid") setIssuesOpen(true);
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
      {publishedVersion === null ? (
        <Badge variant="secondary" className="hidden sm:inline-flex">
          Draft
        </Badge>
      ) : (
        <Popover>
          <PopoverTrigger
            render={
              <button
                type="button"
                aria-label="Show published versions"
                className="hidden rounded-full outline-none focus-visible:ring-3 focus-visible:ring-ring/50 sm:inline-flex"
              />
            }
          >
            <Badge variant="secondary">
              {unpublished
                ? `Published v${publishedVersion} · unpublished changes`
                : `Published v${publishedVersion}`}
              <ChevronDown aria-hidden className="size-3" />
            </Badge>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-[320px] max-w-[calc(100vw-1rem)]">
            <VersionsList />
          </PopoverContent>
        </Popover>
      )}
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
        <Button className="h-9" disabled={busy !== null} onClick={() => void doRun()}>
          <Play aria-hidden /> {busy === "run" ? "Checking…" : "Run"}
        </Button>
        <Button
          variant="outline"
          className="h-9"
          disabled={busy !== null || !unpublished}
          onClick={() => void doPublish()}
        >
          <Rocket aria-hidden /> {busy === "publish" ? "Publishing…" : "Publish"}
        </Button>
        <TestDialog open={runOpen} onOpenChange={setRunOpen} onOutcome={onOutcome} />
        <DropdownMenu>
          <DropdownMenuTrigger render={<Button variant="outline" className="h-9" />}>
            <MoreHorizontal aria-hidden /> More actions
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuItem disabled={busy !== null || !dirty} onClick={() => void doSave()}>
              <Save aria-hidden /> {busy === "save" ? "Saving…" : "Save"}
              <DropdownMenuShortcut>Ctrl+S</DropdownMenuShortcut>
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => openVariables()}>
              <Variable aria-hidden /> Variables
              <DropdownMenuShortcut>{variableCount}</DropdownMenuShortcut>
            </DropdownMenuItem>
            <DropdownMenuItem onClick={exportFlow}>
              <Download aria-hidden /> Export as file
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              variant="destructive"
              disabled={busy !== null || publishedVersion === null}
              onClick={() => setUnpublishOpen(true)}
            >
              <CircleOff aria-hidden /> Unpublish
              {publishedVersion === null && <DropdownMenuShortcut>Not published</DropdownMenuShortcut>}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <UnpublishDialog open={unpublishOpen} onOpenChange={setUnpublishOpen} />
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
