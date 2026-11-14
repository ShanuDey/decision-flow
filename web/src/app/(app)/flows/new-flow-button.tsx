"use client";

import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

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
import { errorToast } from "@/lib/api-error";
import { call } from "@/lib/call";
import { createFlow } from "@/lib/api/client";

export function NewFlowButton() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    setBusy(true);
    const result = await call(createFlow({ name: trimmed }));
    if (!result.ok) {
      setBusy(false);
      errorToast("Could not create the flow", result.error);
      return;
    }
    router.push(`/flows/${result.data.id}`);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button className="h-10" />}>
        <Plus aria-hidden /> New flow
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>New flow</DialogTitle>
            <DialogDescription>It starts with a Start and an End node.</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <Label htmlFor="flow-name">Name</Label>
            <Input
              id="flow-name"
              value={name}
              maxLength={120}
              autoFocus
              required
              onChange={(e) => setName(e.target.value)}
              className="h-10"
            />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={busy || !name.trim()} className="h-10">
              {busy ? "Creating…" : "Create flow"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
