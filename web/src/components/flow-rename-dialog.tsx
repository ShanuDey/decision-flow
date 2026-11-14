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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { renameFlow } from "@/lib/api/client";
import { call } from "@/lib/call";

export function FlowRenameDialog({
  flowId,
  currentName,
  onRenamed,
  trigger,
  open: controlledOpen,
  onOpenChange,
}: {
  flowId: string;
  currentName: string;
  onRenamed: (name: string) => void;
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
  const [name, setName] = useState(currentName);
  const [busy, setBusy] = useState(false);
  const trimmed = name.trim();

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!trimmed || trimmed === currentName) return;
    setBusy(true);
    const result = await call(renameFlow(flowId, { name: trimmed }));
    if (!result.ok) {
      setBusy(false);
      toast.error(`Could not rename the flow: ${result.error.message}`);
      return;
    }
    setOpen(false);
    setBusy(false);
    onRenamed(result.data.name);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (next) setName(currentName);
        setOpen(next);
      }}
    >
      {trigger && <DialogTrigger render={trigger} />}
      <DialogContent>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>Rename flow</DialogTitle>
            <DialogDescription>Your draft and its history are not affected.</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <Label htmlFor={`rename-flow-${flowId}`}>Name</Label>
            <Input
              id={`rename-flow-${flowId}`}
              value={name}
              maxLength={120}
              autoFocus
              required
              onChange={(e) => setName(e.target.value)}
              className="h-10"
            />
          </div>
          <DialogFooter>
            <Button
              type="submit"
              disabled={busy || !trimmed || trimmed === currentName}
              className="h-10"
            >
              {busy ? "Renaming…" : "Rename"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
