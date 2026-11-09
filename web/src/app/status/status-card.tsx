"use client";

import { CircleCheck, CircleMinus, CircleX, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { ready } from "@/lib/api/client";
import type { ReadyResponse as Ready } from "@/lib/api/models";
import { ReadyResponse as ReadySchema } from "@/lib/api/zod";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

type Status =
  | { kind: "loading" }
  | { kind: "misconfigured" }
  | { kind: "unreachable"; checkedAt: Date }
  | { kind: "reachable"; ready: Ready; checkedAt: Date };

const LABELS: Record<string, string> = { postgres: "Postgres", mlflow: "MLflow" };

// /ready answers 503 with the same JSON body, so any HTTP response proves the API is reachable.
async function fetchStatus(signal: AbortSignal): Promise<Status> {
  if (!API_URL) return { kind: "misconfigured" };
  try {
    const res = await ready({ signal, cache: "no-store" });
    return { kind: "reachable", ready: ReadySchema.parse(res.data), checkedAt: new Date() };
  } catch {
    return { kind: "unreachable", checkedAt: new Date() };
  }
}

type RowState = "ok" | "failed" | "unknown" | "checking";

function StatusIcon({ state }: { state: RowState }) {
  switch (state) {
    case "ok":
      return <CircleCheck className="size-4 text-emerald-600 dark:text-emerald-400" aria-hidden />;
    case "failed":
      return <CircleX className="size-4 text-red-600 dark:text-red-400" aria-hidden />;
    case "unknown":
      return <CircleMinus className="size-4 text-zinc-500" aria-hidden />;
    case "checking":
      return <CircleMinus className="size-4 animate-pulse text-zinc-400" aria-hidden />;
  }
}

function Indicator({ state, text }: { state: RowState; text: string }) {
  return (
    <span className="flex items-center gap-2">
      <StatusIcon state={state} />
      {text}
    </span>
  );
}

function Row({ label, state, text }: { label: string; state: RowState; text: string }) {
  return (
    <li className="flex items-center justify-between py-2">
      <span>{label}</span>
      <Indicator state={state} text={text} />
    </li>
  );
}

function rowsFor(status: Status): { label: string; state: RowState; text: string }[] {
  if (status.kind === "loading") {
    return ["API", "Postgres", "MLflow"].map((label) => ({
      label,
      state: "checking",
      text: "Checking…",
    }));
  }
  if (status.kind === "unreachable" || status.kind === "misconfigured") {
    return [
      {
        label: "API",
        state: "failed",
        text: status.kind === "unreachable" ? "Unreachable" : "URL not configured",
      },
      { label: "Postgres", state: "unknown", text: "Unknown" },
      { label: "MLflow", state: "unknown", text: "Unknown" },
    ];
  }
  return [
    { label: "API", state: "ok", text: "Reachable" },
    ...Object.entries(status.ready.checks).map(([name, value]) => ({
      label: LABELS[name] ?? name,
      state: (value === "ok" ? "ok" : "failed") as RowState,
      text: value === "ok" ? "OK" : "Unavailable",
    })),
  ];
}

function summary(status: Status): { state: RowState; text: string } {
  if (status.kind === "loading") return { state: "checking", text: "Checking…" };
  if (status.kind === "unreachable") return { state: "failed", text: "Unreachable" };
  if (status.kind === "misconfigured") return { state: "failed", text: "Misconfigured" };
  return status.ready.status === "ok"
    ? { state: "ok", text: "All OK" }
    : { state: "failed", text: "Degraded" };
}

export function StatusCard() {
  const [status, setStatus] = useState<Status>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    fetchStatus(controller.signal).then((result) => {
      if (!controller.signal.aborted) setStatus(result);
    });
    return () => controller.abort();
  }, []);

  function recheck() {
    setStatus({ kind: "loading" });
    fetchStatus(new AbortController().signal).then(setStatus);
  }

  const total = summary(status);
  const loading = status.kind === "loading";

  return (
    <section
      aria-labelledby="status-heading"
      className="w-full max-w-md rounded-lg border border-zinc-200 p-6 dark:border-zinc-800"
    >
      <div className="flex items-center justify-between">
        <h2 id="status-heading" className="font-medium">
          System status
        </h2>
        <Indicator {...total} />
      </div>

      <ul className="mt-4 divide-y divide-zinc-200 dark:divide-zinc-800" aria-live="polite">
        {rowsFor(status).map((row) => (
          <Row key={row.label} {...row} />
        ))}
      </ul>

      <div className="mt-4 flex items-center justify-between text-sm text-zinc-500">
        <span>
          {"checkedAt" in status ? `Checked ${status.checkedAt.toLocaleTimeString()}` : ""}
        </span>
        <button
          type="button"
          disabled={loading}
          onClick={recheck}
          className="flex items-center gap-2 rounded-md border border-zinc-300 px-3 py-1.5 text-zinc-900 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-50 dark:hover:bg-zinc-900"
        >
          <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} aria-hidden />
          Recheck
        </button>
      </div>
    </section>
  );
}
