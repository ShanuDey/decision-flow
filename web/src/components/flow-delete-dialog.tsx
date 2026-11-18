"use client";

import Link from "next/link";
import { type ReactElement, useEffect, useState } from "react";
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
import { deleteFlow, listCallers } from "@/lib/api/client";
import { errorToast } from "@/lib/api-error";
import { type Caller, callersOf } from "@/lib/callers";
import { call } from "@/lib/call";
import { type DeleteMode, deleteCopy } from "@/lib/delete-copy";

export function FlowDeleteDialog({
  flowId,
  name,
  mode,
  onDeleted,
  trigger,
  open: controlledOpen,
  onOpenChange,
}: {
  flowId: string;
  name: string;
  mode: DeleteMode;
  onDeleted: () => void;
  trigger?: ReactElement;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const [innerOpen, setInnerOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [callers, setCallers] = useState<Caller[]>([]);
  const open = controlledOpen ?? innerOpen;
  const setOpen = (next: boolean) => {
    if (!next) setCallers([]);
    setInnerOpen(next);
    onOpenChange?.(next);
  };

  useEffect(() => {
    if (!open) return;
    let stale = false;
    call(listCallers(flowId)).then((result) => {
      if (!stale && result.ok) setCallers(result.data.items);
    });
    return () => {
      stale = true;
    };
  }, [open, flowId]);

  async function confirm() {
    setBusy(true);
    const result = await call(deleteFlow(flowId, callers.length > 0 ? { force: true } : undefined));
    setBusy(false);
    if (!result.ok) {
      if (result.error.code === "flow_in_use") {
        setCallers(callersOf(result.error.details));
        return;
      }
      errorToast("Could not delete the flow", result.error);
      return;
    }
    setOpen(false);
    toast.success(`Deleted ${name}`);
    onDeleted();
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {trigger && <DialogTrigger render={trigger} />}
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete flow</DialogTitle>
          <DialogDescription>{deleteCopy(mode, name)}</DialogDescription>
        </DialogHeader>
        {callers.length > 0 && (
          <div role="alert" className="flex flex-col gap-2 rounded-lg border border-red-600/40 p-3 text-sm">
            <p>
              {callers.length === 1 ? "1 flow calls" : `${callers.length} flows call`} this one in a Subflow
              node. They will fail until you update them:
            </p>
            <ul className="list-disc pl-5">
              {callers.map((caller) => (
                <li key={caller.id}>
                  <Link href={`/flows/${caller.id}`} className="underline" target="_blank">
                    {caller.name}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
        <DialogFooter>
          <Button variant="destructive" disabled={busy} onClick={confirm} className="h-10">
            {busy ? "Deleting…" : callers.length > 0 ? "Delete anyway" : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
