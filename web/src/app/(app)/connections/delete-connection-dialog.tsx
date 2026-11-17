"use client";

import Link from "next/link";
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
import { deleteConnection } from "@/lib/api/client";
import { errorToast } from "@/lib/api-error";
import { call } from "@/lib/call";

interface FlowRef {
  id: string;
  name: string;
}

function flowsOf(details: Record<string, unknown>): FlowRef[] {
  const raw = details.flows;
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((f) =>
    f && typeof f.id === "string" && typeof f.name === "string" ? [{ id: f.id, name: f.name }] : [],
  );
}

export function DeleteConnectionDialog({ id, name }: { id: string; name: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [flows, setFlows] = useState<FlowRef[]>([]);

  function change(next: boolean) {
    setOpen(next);
    if (!next) setFlows([]);
  }

  async function confirm() {
    setBusy(true);
    const result = await call(deleteConnection(id, flows.length > 0 ? { force: true } : undefined));
    setBusy(false);
    if (!result.ok) {
      if (result.error.code === "connection_in_use") {
        setFlows(flowsOf(result.error.details));
        return;
      }
      errorToast("Could not delete the connection", result.error);
      return;
    }
    change(false);
    toast.success(`Deleted ${name}`);
    router.refresh();
  }

  return (
    <Dialog open={open} onOpenChange={change}>
      <DialogTrigger
        render={
          <Button variant="ghost" size="sm">
            Delete
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete connection</DialogTitle>
          <DialogDescription>
            {name} and its saved credentials are removed for good. A node that uses it fails until you pick
            another connection.
          </DialogDescription>
        </DialogHeader>
        {flows.length > 0 && (
          <div role="alert" className="flex flex-col gap-2 rounded-lg border border-red-600/40 p-3 text-sm">
            <p>{flows.length === 1 ? "1 flow uses" : `${flows.length} flows use`} this connection:</p>
            <ul className="list-disc pl-5">
              {flows.map((flow) => (
                <li key={flow.id}>
                  <Link href={`/flows/${flow.id}`} className="underline" target="_blank">
                    {flow.name}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
        <DialogFooter>
          <Button variant="destructive" disabled={busy} onClick={confirm} className="h-10">
            {busy ? "Deleting…" : flows.length > 0 ? "Delete anyway" : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
