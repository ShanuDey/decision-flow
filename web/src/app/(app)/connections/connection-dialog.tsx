"use client";

import {
  ArrowLeft,
  Braces,
  ExternalLink,
  Eye,
  EyeOff,
  KeyRound,
  type LucideIcon,
  Plug,
  Search,
  Sparkles,
  UserRound,
} from "lucide-react";
import { useState } from "react";
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
import { createConnection, updateConnection } from "@/lib/api/client";
import type { ConnectionSummary, ConnectionTypeInfo } from "@/lib/api/models";
import { errorToast } from "@/lib/api-error";
import { type ApiFailure, type ApiResult, call } from "@/lib/call";
import {
  formProblem,
  groupTypes,
  NAME_MAX,
  payloadValues,
  suggestName,
  VALUE_MAX,
} from "@/lib/connections";
import { cn } from "@/lib/utils";

type Props =
  | { mode: "add"; types: ConnectionTypeInfo[]; existing: string[]; onSaved: () => void }
  | { mode: "edit"; type: ConnectionTypeInfo; connection: ConnectionSummary; onSaved: () => void };

const ICONS: Record<string, LucideIcon> = {
  sparkles: Sparkles,
  "key-round": KeyRound,
  "user-round": UserRound,
  braces: Braces,
};

function TypeIcon({ name, className }: { name: string; className?: string }) {
  const Icon = ICONS[name] ?? Plug;
  return <Icon className={className} aria-hidden />;
}

async function save(result: Promise<ApiResult<unknown>>): Promise<ApiFailure | null> {
  const done = await result;
  return done.ok ? null : done.error;
}

function initialValues(props: Props): Record<string, string> {
  return props.mode === "edit" ? { ...props.connection.config } : {};
}

function TypeCard({ type, onPick }: { type: ConnectionTypeInfo; onPick: () => void }) {
  return (
    <div className="flex flex-col rounded-lg border focus-within:ring-2 focus-within:ring-ring/50 hover:border-foreground/30">
      <button
        type="button"
        onClick={onPick}
        className="flex flex-1 items-start gap-3 rounded-lg p-3 text-left outline-none"
      >
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted">
          <TypeIcon name={type.icon} className="size-4" />
        </span>
        <span className="flex min-w-0 flex-col gap-0.5">
          <span className="text-sm font-medium">{type.name}</span>
          <span className="text-xs text-muted-foreground">{type.description}</span>
        </span>
      </button>
      {type.docs_url && (
        <a
          href={type.docs_url}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1 px-3 pb-2 pl-15 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
        >
          Docs <ExternalLink className="size-3" aria-hidden />
        </a>
      )}
    </div>
  );
}

function Gallery({ types, onPick }: { types: ConnectionTypeInfo[]; onPick: (id: string) => void }) {
  const [query, setQuery] = useState("");
  const { builtin, custom } = groupTypes(types, query);
  const sections = [
    { label: "Built-in", items: builtin },
    { label: "Custom", items: custom },
  ].filter((section) => section.items.length > 0);

  return (
    <div className="flex flex-col gap-4">
      <DialogHeader>
        <DialogTitle>Add connection</DialogTitle>
        <DialogDescription>
          Pick the service to connect. Use Custom for a service that is not listed.
        </DialogDescription>
      </DialogHeader>
      <div className="flex h-9 items-center gap-2 rounded-lg border border-input px-2.5 focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50">
        <Search className="size-3.5 text-muted-foreground" aria-hidden />
        <input
          aria-label="Search connection types"
          placeholder="Search"
          value={query}
          autoFocus
          onChange={(e) => setQuery(e.target.value)}
          className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        />
      </div>
      <div className="flex max-h-[min(420px,55vh)] flex-col gap-4 overflow-y-auto">
        {sections.length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">No connection types match.</p>
        )}
        {sections.map((section) => (
          <div key={section.label} role="group" aria-label={section.label} className="flex flex-col gap-2">
            <p className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
              {section.label}
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {section.items.map((type) => (
                <TypeCard key={type.id} type={type} onPick={() => onPick(type.id)} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function hostsHint(type: ConnectionTypeInfo): string | null {
  if (type.hosts.length > 0) return `Credentials are only ever sent to ${type.hosts.join(", ")}.`;
  const from = type.fields.find((f) => f.name === type.hosts_from);
  return from ? `Credentials are only ever sent to the host of the ${from.label}.` : null;
}

export function ConnectionDialog(props: Props) {
  const editing = props.mode === "edit";
  const [open, setOpen] = useState(false);
  const [typeId, setTypeId] = useState(props.mode === "edit" ? props.type.id : "");
  // Null until the user types a name; the suggestion shows meanwhile.
  const [typed, setTyped] = useState<string | null>(props.mode === "edit" ? props.connection.name : null);
  const [values, setValues] = useState(() => initialValues(props));
  const [busy, setBusy] = useState(false);
  const [shown, setShown] = useState<Record<string, boolean>>({});

  const type = props.mode === "add" ? props.types.find((t) => t.id === typeId) : props.type;
  const name = typed ?? (type && props.mode === "add" ? suggestName(type, values, props.existing) : "");
  const problem = formProblem(type, name, values, editing);

  function reset() {
    setTypeId(props.mode === "edit" ? props.type.id : "");
    setTyped(props.mode === "edit" ? props.connection.name : null);
    setValues(initialValues(props));
    setShown({});
  }

  function change(next: boolean) {
    setOpen(next);
    if (!next) reset();
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (problem || !type) return;
    setBusy(true);
    const payload = payloadValues(type, values, editing);
    const failure =
      props.mode === "edit"
        ? await save(call(updateConnection(props.connection.id, { name: name.trim(), values: payload })))
        : await save(call(createConnection({ type: type.id, name: name.trim(), values: payload })));
    setBusy(false);
    if (failure) {
      errorToast("Could not save the connection", failure);
      return;
    }
    change(false);
    toast.success(editing ? `Saved ${name.trim()}` : `Added ${name.trim()}`);
    props.onSaved();
  }

  const hint = type ? hostsHint(type) : null;

  return (
    <Dialog open={open} onOpenChange={change}>
      <DialogTrigger
        render={
          editing ? (
            <Button variant="ghost" size="sm">
              Edit
            </Button>
          ) : (
            <Button className="h-10">Add connection</Button>
          )
        }
      />
      <DialogContent className={cn(!type && "sm:max-w-2xl")}>
        {props.mode === "add" && !type ? (
          <Gallery types={props.types} onPick={setTypeId} />
        ) : (
          <form onSubmit={submit} className="flex flex-col gap-4">
            <DialogHeader>
              {props.mode === "add" && (
                <button
                  type="button"
                  onClick={() => {
                    setTypeId("");
                    setValues({});
                    setShown({});
                  }}
                  className="flex w-fit items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                >
                  <ArrowLeft className="size-3.5" aria-hidden /> All services
                </button>
              )}
              <DialogTitle className="flex items-center gap-2">
                {type && <TypeIcon name={type.icon} className="size-4" />}
                {editing ? `Edit ${props.connection.name}` : `Add ${type?.name ?? ""}`}
              </DialogTitle>
              <DialogDescription>
                {type?.description} Credentials are encrypted and cannot be read back.
              </DialogDescription>
            </DialogHeader>
            <div className="flex flex-col gap-2">
              <Label htmlFor="connection-name">Name</Label>
              <Input
                id="connection-name"
                value={name}
                maxLength={NAME_MAX}
                placeholder="Production"
                autoFocus
                required
                autoComplete="off"
                onFocus={(e) => typed === null && e.target.select()}
                onChange={(e) => setTyped(e.target.value)}
                className="h-10"
              />
            </div>
            {type?.fields.map((field) => {
              const id = `connection-${field.name}`;
              return (
                <div key={field.name} className="flex flex-col gap-2">
                  <Label htmlFor={id}>
                    {field.label}
                    {(!field.required || field.default) && (
                      <span className="font-normal text-muted-foreground"> (optional)</span>
                    )}
                  </Label>
                  <div className="flex gap-2">
                    <Input
                      id={id}
                      type={
                        field.secret && !shown[field.name] ? "password" : field.format === "url" ? "url" : "text"
                      }
                      value={values[field.name] ?? ""}
                      maxLength={VALUE_MAX}
                      placeholder={
                        field.secret && editing
                          ? "Leave blank to keep the saved value"
                          : field.placeholder || field.default || undefined
                      }
                      autoComplete="off"
                      spellCheck={false}
                      data-1p-ignore
                      onChange={(e) => setValues((current) => ({ ...current, [field.name]: e.target.value }))}
                      className="h-10 font-mono"
                    />
                    {field.secret && (
                      <Button
                        type="button"
                        variant="outline"
                        size="icon"
                        aria-label={shown[field.name] ? `Hide ${field.label}` : `Show ${field.label}`}
                        aria-pressed={shown[field.name] === true}
                        onClick={() => setShown((current) => ({ ...current, [field.name]: !current[field.name] }))}
                        className="size-10 shrink-0"
                      >
                        {shown[field.name] ? <EyeOff aria-hidden /> : <Eye aria-hidden />}
                      </Button>
                    )}
                  </div>
                  {field.help && <p className="text-xs text-muted-foreground">{field.help}</p>}
                </div>
              );
            })}
            {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
            <DialogFooter>
              <Button type="submit" disabled={busy || problem !== null} className="h-10">
                {busy ? "Saving…" : editing ? "Save" : "Add"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
