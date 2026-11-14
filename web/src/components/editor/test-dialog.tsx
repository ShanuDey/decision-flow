"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { errorText, type FieldIssue } from "@/lib/call";
import type { StartData } from "@/lib/graph/types";

import { type RunOutcome, runTest } from "./actions";
import { FieldError, Labeled, TypedValueInput } from "./fields";
import { useEditor } from "./store";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onOutcome: (outcome: RunOutcome) => void;
}

export function TestDialog({ open, onOpenChange, onOutcome }: Props) {
  const start = useEditor((s) => s.nodes.find((n) => n.type === "start"));
  const inputs = (start?.data.config as StartData | undefined)?.inputs ?? [];

  const [values, setValues] = useState<Record<string, unknown>>({});
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<FieldIssue[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setErrors([]);
    setMessage(null);
    const input = Object.fromEntries(Object.entries(values).filter(([, v]) => v !== undefined));
    const outcome = await runTest(input);
    setBusy(false);
    if (!outcome) return;
    if (outcome.kind === "rejected" && outcome.error.code === "invalid_input") {
      const list = outcome.error.details.errors;
      setErrors(
        Array.isArray(list)
          ? list.map((e) => ({ code: "", message: String(e.message), node_id: null, field: String(e.field) }))
          : [],
      );
      return; // keep the dialog open so the values can be fixed
    }
    if (outcome.kind === "rejected") setMessage(errorText(outcome.error));
    onOutcome(outcome);
    if (outcome.kind === "finished") onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-md">
        <form onSubmit={submit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>Test run</DialogTitle>
            <DialogDescription>
              Runs your current draft with these inputs. Unsaved changes are saved first.
            </DialogDescription>
          </DialogHeader>
          {inputs.length === 0 && (
            <p className="text-sm text-muted-foreground">This flow takes no inputs.</p>
          )}
          {inputs.map((input, i) => (
            <Labeled
              key={i}
              id={`test-${i}`}
              label={`${input.name || "(unnamed)"} · ${input.type}${input.required === false ? "" : " · required"}`}
              issue={errors.find((e) => e.field === input.name)}
            >
              <TypedValueInput
                id={`test-${i}`}
                type={input.type}
                values={input.values}
                value={values[input.name]}
                onChange={(value) => setValues((v) => ({ ...v, [input.name]: value }))}
              />
            </Labeled>
          ))}
          {errors.length > 0 && !inputs.some((i) => errors.some((e) => e.field === i.name)) &&
            errors.map((e, i) => <FieldError key={i} issue={e} />)}
          {message && <p role="alert" className="text-sm text-red-700 dark:text-red-400">{message}</p>}
          <DialogFooter>
            <Button type="submit" disabled={busy} className="h-10">
              {busy ? "Running…" : "Run"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
