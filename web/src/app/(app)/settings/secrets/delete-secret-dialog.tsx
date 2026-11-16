"use client";

import { useRouter } from "next/navigation";
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
import { deleteSecret } from "@/lib/api/client";
import { errorToast } from "@/lib/api-error";
import { call } from "@/lib/call";

export function DeleteSecretDialog({ name }: { name: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  async function confirm() {
    setBusy(true);
    const result = await call(deleteSecret(name));
    setBusy(false);
    if (!result.ok) {
      errorToast("Could not delete the secret", result.error);
      return;
    }
    setOpen(false);
    toast.success(`Deleted ${name}`);
    router.refresh();
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant="ghost" size="sm">Delete</Button>} />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete secret</DialogTitle>
          <DialogDescription>
            {name} is removed for good. A flow that uses it fails until you add it again.
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
