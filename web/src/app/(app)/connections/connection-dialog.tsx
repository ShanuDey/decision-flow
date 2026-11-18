"use client";

import { ArrowLeft, Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { CatalogGallery, CatalogIcon } from "@/components/catalog/catalog-gallery";
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
  NAME_MAX,
  payloadValues,
  type Prefill,
  suggestName,
  VALUE_MAX,
} from "@/lib/connections";
import type { CatalogItem } from "@/lib/catalog";
import { cn } from "@/lib/utils";

type Props =
  | {
      mode: "add";
      types: ConnectionTypeInfo[];
      existing: string[];
      initial?: Prefill;
      onSaved: () => void;
    }
  | { mode: "edit"; type: ConnectionTypeInfo; connection: ConnectionSummary; onSaved: () => void };

async function save(result: Promise<ApiResult<unknown>>): Promise<ApiFailure | null> {
  const done = await result;
  return done.ok ? null : done.error;
}

function initialValues(props: Props): Record<string, string> {
  if (props.mode === "edit") return { ...props.connection.config };
  return { ...props.initial?.values };
}

const GROUPS = ["Built-in", "Custom"];

function typeItems(types: ConnectionTypeInfo[]): CatalogItem[] {
  return types.map((t) => ({
    id: t.id,
    name: t.name,
    description: t.description,
    icon: t.icon,
    docsUrl: t.docs_url,
    group: t.category === "custom" ? "Custom" : "Built-in",
    tags: [],
  }));
}

function hostsHint(type: ConnectionTypeInfo): string | null {
  if (type.hosts.length > 0) return `Credentials are only ever sent to ${type.hosts.join(", ")}.`;
  const from = type.fields.find((f) => f.name === type.hosts_from);
  return from ? `Credentials are only ever sent to the host of the ${from.label}.` : null;
}

export function ConnectionDialog(props: Props) {
  const editing = props.mode === "edit";
  // A prefilled link opens the dialog on its type.
  const [open, setOpen] = useState(props.mode === "add" && props.initial !== undefined);
  const [typeId, setTypeId] = useState(
    props.mode === "edit" ? props.type.id : (props.initial?.typeId ?? ""),
  );
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
    setValues(props.mode === "edit" ? { ...props.connection.config } : {});
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
          <CatalogGallery
            title="Add connection"
            description="Pick the service to connect. Use Custom for a service that is not listed."
            items={typeItems(props.types)}
            order={GROUPS}
            onPick={setTypeId}
          />
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
                {type && <CatalogIcon name={type.icon} className="size-4" />}
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
