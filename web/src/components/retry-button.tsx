"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { retry } from "@/lib/retry";

async function waitForApi(): Promise<void> {
  const res = await fetch("/warm/ready", { cache: "no-store" });
  if (!res.ok) throw new Error(`API not ready (${res.status})`);
}

export function RetryButton() {
  const router = useRouter();
  const [refreshing, startTransition] = useTransition();
  const [waiting, setWaiting] = useState(false);
  const [gaveUp, setGaveUp] = useState(false);
  const busy = waiting || refreshing;

  async function onClick() {
    setWaiting(true);
    setGaveUp(false);
    try {
      await retry(waitForApi, { attempts: 6 });
      startTransition(() => router.refresh());
    } catch {
      setGaveUp(true);
    } finally {
      setWaiting(false);
    }
  }

  return (
    <>
      <Button onClick={onClick} disabled={busy}>
        {busy && <Loader2 className="animate-spin" aria-hidden />}
        {busy ? "Waking the server…" : "Try again"}
      </Button>
      {gaveUp && (
        <span role="status" className="text-muted-foreground">
          Still starting. Try again in a moment.
        </span>
      )}
    </>
  );
}
