"use client";

import { Search, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState, useSyncExternalStore } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createFlow, listConnections, listConnectionTypes, listTemplates } from "@/lib/api/client";
import type { Template } from "@/lib/api/models";
import { errorToast } from "@/lib/api-error";
import { call, errorText } from "@/lib/call";
import {
  ALL_CATEGORIES,
  categoriesOf,
  filterTemplates,
  flatTemplates,
  groupByCategory,
} from "@/lib/templates/filter";
import { type ConnectionOption, connectionOptions } from "@/lib/connections";
import {
  applyConnections,
  type ConnectionNeed,
  type ImportResult,
  parseFlowFile,
  planConnections,
} from "@/lib/graph/transfer";
import { cn } from "@/lib/utils";

import { FlowPreview } from "./flow-preview";
import { ImportConnectionsDialog } from "./import-connections-dialog";

const BLANK = "blank";
const BLANK_NAME = "Untitled flow";

type Loaded = { state: "loading" } | { state: "error"; message: string } | { state: "ready"; items: Template[] };

let cachedItems: Template[] | null = null;

const DESKTOP = "(min-width: 40rem)";

function useIsDesktop() {
  return useSyncExternalStore(
    (notify) => {
      const query = window.matchMedia(DESKTOP);
      query.addEventListener("change", notify);
      return () => query.removeEventListener("change", notify);
    },
    () => window.matchMedia(DESKTOP).matches,
    () => true,
  );
}

interface PendingImport {
  fileName: string;
  parsed: Extract<ImportResult, { ok: true }>;
  needs: ConnectionNeed[];
  options: ConnectionOption[];
  typeNames: Record<string, string>;
}

export function TemplatePicker({ trigger }: { trigger: React.ReactElement }) {
  const router = useRouter();
  const isDesktop = useIsDesktop();
  const [open, setOpen] = useState(false);
  const [loaded, setLoaded] = useState<Loaded>(
    cachedItems ? { state: "ready", items: cachedItems } : { state: "loading" },
  );
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState(ALL_CATEGORIES);
  const [selected, setSelected] = useState(BLANK);
  const [name, setName] = useState(BLANK_NAME);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<PendingImport | null>(null);
  const request = useRef(0);
  const fileInput = useRef<HTMLInputElement>(null);
  const filled = useRef(BLANK_NAME);

  const items = loaded.state === "ready" ? loaded.items : [];
  const groups = groupByCategory(filterTemplates(items, query, category));
  const flat = flatTemplates(groups);
  // Looked up in the full list so a search can hide the choice without changing it.
  const template = items.find((t) => t.id === selected) ?? null;
  const active = template ? template.id : BLANK;

  async function load(force = false) {
    if (cachedItems && !force) {
      setLoaded({ state: "ready", items: cachedItems });
      return;
    }
    const id = ++request.current;
    setLoaded({ state: "loading" });
    const result = await call(listTemplates());
    if (id !== request.current) return;
    if (result.ok) {
      cachedItems = result.data.items;
      setLoaded({ state: "ready", items: result.data.items });
    } else {
      setLoaded({ state: "error", message: errorText(result.error) });
    }
  }

  function onOpenChange(next: boolean) {
    setOpen(next);
    if (!next) {
      request.current += 1;
      return;
    }
    setQuery("");
    setCategory(ALL_CATEGORIES);
    setSelected(BLANK);
    setName(BLANK_NAME);
    filled.current = BLANK_NAME;
    setBusy(false);
    void load();
  }

  // The name follows the selection only while the user hasn't edited it.
  function choose(id: string, title: string) {
    setSelected(id);
    if (!name.trim() || name === filled.current) setName(title);
    filled.current = title;
  }

  function chooseId(id: string) {
    const found = items.find((t) => t.id === id);
    choose(found ? found.id : BLANK, found ? found.title : BLANK_NAME);
  }

  function onSearchKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      chooseId(flat[0]?.id ?? BLANK);
      return;
    }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const ids = [BLANK, ...flat.map((t) => t.id)];
    const i = ids.indexOf(active);
    const down = e.key === "ArrowDown";
    chooseId(ids[i < 0 ? (down ? 0 : ids.length - 1) : (i + (down ? 1 : ids.length - 1)) % ids.length]);
  }

  async function importFile(file: File) {
    setBusy(true);
    const parsed = parseFlowFile(await file.text());
    if (!parsed.ok) {
      setBusy(false);
      toast.error(parsed.message);
      return;
    }
    const [list, types] = await Promise.all([call(listConnections()), call(listConnectionTypes())]);
    if (!list.ok) {
      setBusy(false);
      errorToast("Could not check your connections", list.error);
      return;
    }
    if (!types.ok) {
      setBusy(false);
      errorToast("Could not check your connections", types.error);
      return;
    }
    const options = connectionOptions(list.data.items, types.data.items);
    const typeNames = Object.fromEntries(types.data.items.map((t) => [t.id, t.name]));
    const job = {
      fileName: file.name,
      parsed,
      needs: planConnections(parsed.graph, parsed.connections, options),
      options,
      typeNames,
    };
    if (job.needs.length === 0) {
      await finishImport(job, {});
      return;
    }
    setBusy(false);
    setPending(job);
  }

  async function finishImport(job: PendingImport, choices: Record<string, string>) {
    setBusy(true);
    const { parsed, needs, options, fileName } = job;
    const fallback = fileName.replace(/(\.flow)?\.json$/i, "").trim() || BLANK_NAME;
    const graph = applyConnections(parsed.graph, choices, options);
    const result = await call(createFlow({ name: (parsed.name ?? fallback).slice(0, 120), draft: { ...graph } }));
    if (!result.ok) {
      setBusy(false);
      errorToast("Could not import the flow", result.error);
      return;
    }
    if (parsed.clearedSubflows) {
      toast.info(`Pick the flow again in ${parsed.clearedSubflows} subflow node(s); ids are not carried over.`);
    }
    const unset = needs.filter((n) => !choices[n.fileId]).reduce((total, n) => total + n.nodes, 0);
    if (unset) toast.info(`Pick a connection in ${unset} request node(s); the file's ids are not carried over.`);
    router.push(`/flows/${result.data.id}`);
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    setBusy(true);
    const result = await call(createFlow({ name: trimmed, draft: template?.draft }));
    if (!result.ok) {
      setBusy(false);
      errorToast("Could not create the flow", result.error);
      return;
    }
    router.push(`/flows/${result.data.id}`);
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogTrigger render={trigger} />
        <DialogContent className="sm:max-w-3xl">
          <form onSubmit={submit} className="flex flex-col gap-4">
            <DialogHeader>
              <DialogTitle>New flow</DialogTitle>
              <DialogDescription>
                Start from a template or a blank flow. You get your own copy to edit.
              </DialogDescription>
            </DialogHeader>
            <div className="grid h-[min(440px,60vh)] grid-cols-[260px_minmax(0,1fr)] overflow-hidden rounded-lg border max-sm:grid-cols-1 max-sm:grid-rows-[minmax(0,1fr)_auto]">
              <div className="flex min-h-0 flex-col border-r p-2.5 max-sm:border-r-0 max-sm:border-b">
                <div className="flex h-9 items-center gap-2 rounded-lg border border-input px-2.5 focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50">
                  <Search className="size-3.5 text-muted-foreground" aria-hidden />
                  <input
                    aria-label="Search templates"
                    placeholder="Search templates"
                    value={query}
                    autoFocus
                    aria-controls="template-list"
                    aria-activedescendant={rowId(active)}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={onSearchKeyDown}
                    className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                  />
                </div>
                <div role="tablist" aria-label="Category" className="mt-2 flex flex-wrap gap-1">
                  {[ALL_CATEGORIES, ...categoriesOf(items)].map((value) => (
                    <button
                      key={value}
                      type="button"
                      role="tab"
                      aria-selected={category === value}
                      onClick={() => setCategory(value)}
                      className={cn(
                        "rounded-md px-2.5 py-1 text-xs font-medium text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50",
                        category === value && "bg-muted text-foreground",
                      )}
                    >
                      {value === ALL_CATEGORIES ? "All" : value}
                    </button>
                  ))}
                </div>
                <div id="template-list" role="listbox" aria-label="Templates" className="mt-1 min-h-0 flex-1 overflow-y-auto">
                  <Group label="Start fresh">
                    <Row
                      id={rowId(BLANK)}
                      title="Blank flow"
                      summary="Start and End only"
                      selected={active === BLANK}
                      onSelect={() => choose(BLANK, BLANK_NAME)}
                    />
                  </Group>
                  {loaded.state === "loading" && (
                    <p className="px-2.5 py-3 text-sm text-muted-foreground">Loading templates…</p>
                  )}
                  {loaded.state === "error" && (
                    <p role="alert" className="px-2.5 py-3 text-sm text-muted-foreground">
                      Could not load templates: {loaded.message}{" "}
                      <button type="button" onClick={() => void load(true)} className="underline">
                        Retry
                      </button>
                    </p>
                  )}
                  {loaded.state === "ready" && flat.length === 0 && (
                    <p className="px-2.5 py-3 text-sm text-muted-foreground">No templates match your search.</p>
                  )}
                  {groups.map((group) => (
                    <Group key={group.category} label={group.category}>
                      {group.items.map((t) => (
                        <Row
                          key={t.id}
                          id={rowId(t.id)}
                          title={t.title}
                          summary={t.summary}
                          selected={active === t.id}
                          onSelect={() => choose(t.id, t.title)}
                        />
                      ))}
                    </Group>
                  ))}
                </div>
              </div>
              <div className="flex min-h-0 min-w-0 flex-col gap-3 p-4">
                <h3 className="text-base font-semibold">{template ? template.title : "Blank flow"}</h3>
                <div className="min-h-0 flex-1 overflow-hidden rounded-lg border bg-muted/30 max-sm:hidden">
                  {!isDesktop ? null : template ? (
                    <FlowPreview key={template.id} draft={template.draft} />
                  ) : (
                    <p className="grid h-full place-items-center px-4 text-center text-sm text-muted-foreground">
                      A Start node connected to an End node. Add the rest yourself.
                    </p>
                  )}
                </div>
                {template && (
                  <>
                    <p className="text-sm leading-relaxed text-muted-foreground">{template.description}</p>
                    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs max-sm:hidden">
                      <dt className="text-muted-foreground">Inputs</dt>
                      <dd>{template.inputs.join(", ") || "none"}</dd>
                      <dt className="text-muted-foreground">Outputs</dt>
                      <dd>{template.outputs.join(", ") || "none"}</dd>
                    </dl>
                  </>
                )}
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="flow-name">Name</Label>
              <Input
                id="flow-name"
                value={name}
                maxLength={120}
                required
                onChange={(e) => setName(e.target.value)}
                className="h-10"
              />
            </div>
            <DialogFooter>
              <input
                ref={fileInput}
                type="file"
                accept=".json,application/json"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  e.target.value = "";
                  if (file) void importFile(file);
                }}
              />
              <Button
                type="button"
                variant="outline"
                disabled={busy}
                className="h-10 sm:mr-auto"
                onClick={() => fileInput.current?.click()}
              >
                <Upload aria-hidden /> Import file
              </Button>
              <Button type="submit" disabled={busy || !name.trim()} className="h-10">
                {busy ? "Creating…" : "Create flow"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    {pending && (
      <ImportConnectionsDialog
        needs={pending.needs}
        options={pending.options}
        typeNames={pending.typeNames}
        busy={busy}
        onConfirm={(choices) => void finishImport(pending, choices)}
        onCancel={() => setPending(null)}
      />
    )}
    </>
  );
}

function Group({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div role="group" aria-label={label}>
      <p className="px-2.5 pt-2.5 pb-1 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
        {label}
      </p>
      {children}
    </div>
  );
}

const rowId = (id: string) => `template-row-${id}`;

function Row({
  id,
  title,
  summary,
  selected,
  onSelect,
}: {
  id: string;
  title: string;
  summary: string;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <div
      id={id}
      role="option"
      aria-selected={selected}
      onClick={onSelect}
      className={cn("flex cursor-pointer flex-col rounded-lg px-2.5 py-1.5", selected && "bg-muted")}
    >
      <span className="truncate text-sm font-medium">{title}</span>
      <span className="truncate text-xs text-muted-foreground">{summary}</span>
    </div>
  );
}
