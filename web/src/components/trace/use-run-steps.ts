"use client";

import { useCallback, useEffect, useState } from "react";

import { getRunSteps } from "@/lib/api/client";
import type { RunStep } from "@/lib/api/models";
import { type ApiFailure, call } from "@/lib/call";
import { pollDelay } from "@/lib/trace/poll";

export type StepsState =
  | { kind: "loading" }
  | { kind: "pending" }
  | { kind: "timeout" }
  | { kind: "ready"; steps: RunStep[] }
  | { kind: "error"; error: ApiFailure };

// The trace lands shortly after the run ends: 9 checks, about 28 s.
const MAX_POLLS = 8;

const LOADING: StepsState = { kind: "loading" };

export function useRunSteps(runId: string): { state: StepsState; reload: () => void } {
  // Tagged with its run so a result for another run is never shown.
  const [result, setResult] = useState<{ runId: string; state: StepsState } | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const publish = (state: StepsState) => setResult({ runId, state });
    void (async () => {
      for (let poll = 0; poll <= MAX_POLLS; poll++) {
        const response = await call(getRunSteps(runId));
        if (cancelled) return;
        if (!response.ok) {
          publish({ kind: "error", error: response.error });
          return;
        }
        if (!response.data.pending) {
          publish({ kind: "ready", steps: response.data.items });
          return;
        }
        publish({ kind: "pending" });
        if (poll === MAX_POLLS) break;
        await new Promise((resolve) => setTimeout(resolve, pollDelay(poll)));
        if (cancelled) return;
      }
      publish({ kind: "timeout" });
    })();
    return () => {
      cancelled = true;
    };
  }, [runId, attempt]);

  const reload = useCallback(() => {
    setResult(null);
    setAttempt((n) => n + 1);
  }, []);

  return { state: result && result.runId === runId ? result.state : LOADING, reload };
}
