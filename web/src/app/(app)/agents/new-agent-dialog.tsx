"use client";

import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createAgent } from "@/lib/api/client";
import { errorToast } from "@/lib/api-error";
import { call } from "@/lib/call";
import { uniqueName } from "@/lib/agents";

export function NewAgentDialog({ existing }: { existing: string[] }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");

  function change(next: boolean) {
    setOpen(next);
    if (next) setName(uniqueName("Agent", existing));
  }

  async function create() {
    setBusy(true);
    const result = await call(createAgent({ name: name.trim() }));
    if (!result.ok) {
      setBusy(false);
      errorToast("Could not create the agent", result.error);
      return;
    }
    router.push(`/agents/${result.data.id}`);
  }

  return (
    <Dialog open={open} onOpenChange={change}>
      <DialogTrigger
        render={
          <Button className="h-10">
            <Plus aria-hidden /> New agent
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New agent</DialogTitle>
          <DialogDescription>You choose its model and flows on the next page.</DialogDescription>
        </DialogHeader>
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim() && !busy) void create();
          }}
        >
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="new-agent-name">Name</Label>
            <Input
              id="new-agent-name"
              className="h-10"
              value={name}
              maxLength={80}
              autoFocus
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <Button type="submit" className="h-10 self-end" disabled={busy || !name.trim()}>
            {busy ? "Creating…" : "Create"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
