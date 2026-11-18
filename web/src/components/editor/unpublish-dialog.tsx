"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { listCallers, unpublishFlow } from "@/lib/api/client";
import { errorToast } from "@/lib/api-error";
import { type Caller, callersOf } from "@/lib/callers";
import { call } from "@/lib/call";

import { useEditor } from "./store";

export function UnpublishDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const flowId = useEditor((s) => s.flowId);
  const [busy, setBusy] = useState(false);
  const [callers, setCallers] = useState<Caller[]>([]);

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

  function close(next: boolean) {
    if (!next) setCallers([]);
    onOpenChange(next);
  }

  async function confirm() {
    setBusy(true);
    const result = await call(unpublishFlow(flowId, callers.length > 0 ? { force: true } : undefined));
    setBusy(false);
    if (!result.ok) {
      if (result.error.code === "flow_in_use") {
        setCallers(callersOf(result.error.details));
        return;
      }
      if (result.error.code === "not_published") useEditor.getState().markUnpublished();
      errorToast("Could not unpublish the flow", result.error);
      close(false);
      return;
    }
    useEditor.getState().markUnpublished();
    toast.success("Unpublished. Publish again to put it back online.");
    close(false);
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Unpublish flow</DialogTitle>
          <DialogDescription>
            Runs and API calls to the published version will stop working. Your draft and past versions are kept,
            and publishing again brings the flow back.
          </DialogDescription>
        </DialogHeader>
        {callers.length > 0 && (
          <div role="alert" className="flex flex-col gap-2 rounded-lg border border-red-600/40 p-3 text-sm">
            <p>
              {callers.length === 1 ? "1 flow calls" : `${callers.length} flows call`} this one in a Subflow
              node. They will fail until you publish it again:
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
            {busy ? "Unpublishing…" : callers.length > 0 ? "Unpublish anyway" : "Unpublish"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
