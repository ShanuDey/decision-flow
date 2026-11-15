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
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SelectField } from "@/components/ui/select-field";
import { expiryDays, NAME_MAX } from "@/lib/auth/key-request";
import {
  agentKey,
  claudeCodeCommand,
  DEFAULT_AGENT_EXPIRY,
  DEFAULT_AGENT_NAME,
  jsonConfig,
  mcpUrl,
} from "@/lib/auth/mcp-config";
import { ACTIONS, type Action } from "@/lib/auth/scopes";

import { EXPIRY_CHOICES, SCOPES } from "./create-key-dialog";

function CopyBlock({ label, text, hint }: { label: string; text: string; hint?: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      toast.error("Could not copy", { description: "Select the text and copy it by hand" });
    }
  }

  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <Label>{label}</Label>
      <div className="flex items-start gap-2">
        <pre className="min-w-0 flex-1 overflow-x-auto rounded-md border bg-muted p-2 font-mono text-xs">{text}</pre>
        <Button type="button" variant="outline" onClick={copy} className="h-8 shrink-0">
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

export function ConnectAgentDialog({ atLimit }: { atLimit: boolean }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [secret, setSecret] = useState<string | null>(null);
  const [name, setName] = useState(DEFAULT_AGENT_NAME);
  const [actions, setActions] = useState<Action[]>([...ACTIONS]);
  const [expiry, setExpiry] = useState(DEFAULT_AGENT_EXPIRY);

  function change(next: boolean) {
    setOpen(next);
    if (!next) {
      setSecret(null);
      setName(DEFAULT_AGENT_NAME);
      setActions([...ACTIONS]);
      setExpiry(DEFAULT_AGENT_EXPIRY);
    }
  }

  function toggle(action: Action, on: boolean) {
    setActions((current) => ACTIONS.filter((a) => (a === action ? on : current.includes(a))));
  }

  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim() || actions.length === 0) return;
    setBusy(true);
    try {
      const response = await fetch("/api/keys", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(agentKey(name.trim(), actions, expiryDays(expiry))),
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

  const url = mcpUrl(typeof window === "undefined" ? "" : window.location.origin);

  return (
    <Dialog open={open} onOpenChange={change}>
      <DialogTrigger
        render={
          <Button variant="outline" className="h-10" disabled={atLimit}>
            Connect an AI agent
          </Button>
        }
      />
      <DialogContent className="sm:max-w-xl">
        {secret ? (
          <div className="flex min-w-0 flex-col gap-4">
            <DialogHeader>
              <DialogTitle>Connect your agent</DialogTitle>
              <DialogDescription>
                The key below is not shown again. Anyone with it can read, change and run your flows.
              </DialogDescription>
            </DialogHeader>
            <CopyBlock label="API key" text={secret} />
            <CopyBlock
              label="Claude Code"
              text={claudeCodeCommand(url, secret)}
              hint="Run this in a terminal."
            />
            <CopyBlock
              label="Other clients"
              text={jsonConfig(url, secret)}
              hint="For clients that take a server URL and headers. Check your client's docs for the file and field names."
            />
            <p className="text-xs text-muted-foreground">
              After a quiet spell the server can take a few minutes to wake up. If the first call fails, try again shortly.
            </p>
            <DialogFooter>
              <Button type="button" onClick={() => change(false)} className="h-10">
                Done
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <form onSubmit={create} className="flex flex-col gap-4">
            <DialogHeader>
              <DialogTitle>Connect an AI agent</DialogTitle>
              <DialogDescription>
                Creates a key and shows ready-to-paste setup for your agent. Give each agent its own name and only the
                scopes it needs, so you can revoke one without affecting the others.
              </DialogDescription>
            </DialogHeader>
            <div className="flex flex-col gap-2">
              <Label htmlFor="agent-name">Agent name</Label>
              <Input
                id="agent-name"
                value={name}
                maxLength={NAME_MAX}
                placeholder="Claude Code on my laptop"
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
                    id={`agent-scope-${action}`}
                    checked={actions.includes(action)}
                    onCheckedChange={(on) => toggle(action, on)}
                    className="mt-0.5"
                  />
                  <div className="flex flex-col">
                    <Label htmlFor={`agent-scope-${action}`}>{SCOPES[action].title}</Label>
                    <span className="text-xs text-muted-foreground">{SCOPES[action].hint}</span>
                  </div>
                </div>
              ))}
            </fieldset>
            <div className="flex flex-col gap-2">
              <Label htmlFor="agent-expiry">Expires</Label>
              <SelectField id="agent-expiry" value={expiry} onValueChange={setExpiry} options={EXPIRY_CHOICES} />
            </div>
            <DialogFooter>
              <Button type="submit" disabled={busy || !name.trim() || actions.length === 0} className="h-10">
                {busy ? "Creating…" : "Create key and show setup"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
