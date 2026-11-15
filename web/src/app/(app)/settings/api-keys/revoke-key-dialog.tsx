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
import { authClient } from "@/lib/auth/client";

export function RevokeKeyDialog({ keyId, name }: { keyId: string; name: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  async function confirm() {
    setBusy(true);
    const { error } = await authClient.apiKey.delete({ keyId });
    setBusy(false);
    if (error) {
      toast.error("Could not revoke the key", { description: error.message });
      return;
    }
    setOpen(false);
    toast.success(`Revoked ${name}`);
    router.refresh();
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant="ghost" size="sm">Revoke</Button>} />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Revoke key</DialogTitle>
          <DialogDescription>
            Anything using {name} stops working right away. This cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="destructive" disabled={busy} onClick={confirm} className="h-10">
            {busy ? "Revoking…" : "Revoke"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
