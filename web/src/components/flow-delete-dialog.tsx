"use client";

import { type ReactElement, useState } from "react";
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
import { deleteFlow } from "@/lib/api/client";
import { errorToast } from "@/lib/api-error";
import { call } from "@/lib/call";

export function FlowDeleteDialog({
  flowId,
  name,
  onDeleted,
  trigger,
  open: controlledOpen,
  onOpenChange,
}: {
  flowId: string;
  name: string;
  onDeleted: () => void;
  trigger?: ReactElement;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const [innerOpen, setInnerOpen] = useState(false);
  const open = controlledOpen ?? innerOpen;
  const setOpen = (next: boolean) => {
    setInnerOpen(next);
    onOpenChange?.(next);
  };
  const [busy, setBusy] = useState(false);

  async function confirm() {
    setBusy(true);
    const result = await call(deleteFlow(flowId));
    setBusy(false);
    if (!result.ok) {
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
          <DialogDescription>
            This deletes “{name}” and all of its runs. It cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="destructive" disabled={busy} onClick={confirm} className="h-10">
            {busy ? "Deleting…" : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
