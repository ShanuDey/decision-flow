"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { SelectField } from "@/components/ui/select-field";
import {
  DEFAULT_EXPIRY,
  EXPIRY_OPTIONS,
  expiryDays,
  MAX_KEYS,
  NAME_MAX,
} from "@/lib/auth/key-request";
import { ACTIONS, type Action } from "@/lib/auth/scopes";

export const SCOPES: Record<Action, { title: string; hint: string }> = {
  read: { title: "Read", hint: "List and view flows and runs" },
  write: { title: "Write", hint: "Create, edit, publish and delete flows" },
  run: { title: "Run", hint: "Run flows" },
};

export const EXPIRY_CHOICES =EXPIRY_OPTIONS.map(({ value, label }) => ({ value, label }));

export function CreateKeyDialog({ atLimit }: { atLimit: boolean }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [actions, setActions] = useState<Action[]>(["read"]);
  const [expiry, setExpiry] = useState(DEFAULT_EXPIRY);
  const [busy, setBusy] = useState(false);
  const [secret, setSecret] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const trimmed = name.trim();

  function change(next: boolean) {
    setOpen(next);
    if (!next) {
      setName("");
      setActions(["read"]);
      setExpiry(DEFAULT_EXPIRY);
      setSecret(null);
      setCopied(false);
    }
  }

  function toggle(action: Action, on: boolean) {
    setActions((current) => (on ? [...current, action] : current.filter((a) => a !== action)));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!trimmed || actions.length === 0) return;
    setBusy(true);
    try {
      const response = await fetch("/api/keys", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: trimmed, actions, expiresInDays: expiryDays(expiry) }),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok || typeof body?.key !== "string") {
        toast.error("Could not create the key", {
          description: typeof body?.message === "string" ? body.message : `Request failed (${response.status})`,
        });
        return;
      }
      setSecret(body.key);
      router.refresh();
    } catch {
      toast.error("Could not create the key", { description: "Cannot reach the server" });
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    if (!secret) return;
    try {
      await navigator.clipboard.writeText(secret);
      setCopied(true);
    } catch {
      toast.error("Could not copy", { description: "Select the key and copy it by hand" });
    }
  }

  return (
    <Dialog open={open} onOpenChange={change}>
      <DialogTrigger
        render={
          <Button className="h-10" disabled={atLimit} title={atLimit ? `Limit of ${MAX_KEYS} keys reached` : undefined}>
            Create key
          </Button>
        }
      />
      <DialogContent>
        {secret ? (
          <div className="flex flex-col gap-4">
            <DialogHeader>
              <DialogTitle>Key created</DialogTitle>
              <DialogDescription>
                Copy it now. It is not shown again, and anyone with it can act as you within its scopes.
              </DialogDescription>
            </DialogHeader>
            <div className="flex gap-2">
              <Input
                readOnly
                value={secret}
                aria-label="API key"
                onFocus={(e) => e.currentTarget.select()}
                className="h-10 font-mono text-xs"
              />
              <Button type="button" variant="outline" onClick={copy} className="h-10">
                {copied ? "Copied" : "Copy"}
              </Button>
            </div>
            <DialogFooter>
              <Button type="button" onClick={() => change(false)} className="h-10">
                Done
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <form onSubmit={submit} className="flex flex-col gap-4">
            <DialogHeader>
              <DialogTitle>Create key</DialogTitle>
              <DialogDescription>Give it only the scopes the caller needs.</DialogDescription>
            </DialogHeader>
            <div className="flex flex-col gap-2">
              <Label htmlFor="key-name">Name</Label>
              <Input
                id="key-name"
                value={name}
                maxLength={NAME_MAX}
                placeholder="CI trigger"
                autoFocus
                required
                onChange={(e) => setName(e.target.value)}
                className="h-10"
              />
            </div>
            <fieldset className="flex flex-col gap-3">
              <legend className="mb-1 text-sm font-medium">Scopes</legend>
              {ACTIONS.map((action) => (
                <div key={action} className="flex items-start gap-3">
                  <Checkbox
                    id={`scope-${action}`}
                    checked={actions.includes(action)}
                    onCheckedChange={(on) => toggle(action, on)}
                    className="mt-0.5"
                  />
                  <div className="flex flex-col">
                    <Label htmlFor={`scope-${action}`}>{SCOPES[action].title}</Label>
                    <span className="text-xs text-muted-foreground">{SCOPES[action].hint}</span>
                  </div>
                </div>
              ))}
            </fieldset>
            <div className="flex flex-col gap-2">
              <Label htmlFor="key-expiry">Expires</Label>
              <SelectField
                id="key-expiry"
                value={expiry}
                onValueChange={setExpiry}
                options={EXPIRY_CHOICES}
              />
            </div>
            <DialogFooter>
              <Button type="submit" disabled={busy || !trimmed || actions.length === 0} className="h-10">
                {busy ? "Creating…" : "Create"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
