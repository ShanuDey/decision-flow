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
import { Label } from "@/components/ui/label";
import { AGENT_KEY, claudeCodeCommand, jsonConfig, mcpUrl } from "@/lib/auth/mcp-config";

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

  function change(next: boolean) {
    setOpen(next);
    if (!next) setSecret(null);
  }

  async function create() {
    setBusy(true);
    try {
      const response = await fetch("/api/keys", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(AGENT_KEY),
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
          <div className="flex flex-col gap-4">
            <DialogHeader>
              <DialogTitle>Connect an AI agent</DialogTitle>
              <DialogDescription>
                Creates a key named “{AGENT_KEY.name}” with read, write and run access, valid for {AGENT_KEY.expiresInDays} days,
                and shows ready-to-paste setup for your agent. Revoke it here at any time.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button type="button" onClick={create} disabled={busy} className="h-10">
                {busy ? "Creating…" : "Create key and show setup"}
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
