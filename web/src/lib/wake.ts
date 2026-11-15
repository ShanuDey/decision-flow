import { after } from "next/server";

import { getConfig } from "./auth/server";
import { API_TIMEOUT_MS } from "./backend-proxy";

export const MIN_GAP_MS = 20_000;
let lastWake = 0;

export function wakeApi(now: number = Date.now()): void {
  if (now - lastWake < MIN_GAP_MS) return;
  after(async () => {
    try {
      await fetch(`${getConfig().apiUrl}/health`, {
        cache: "no-store",
        signal: AbortSignal.timeout(API_TIMEOUT_MS),
      });
    } catch {
      // Best effort; whoever needs the API reports its own failure.
    }
  });
  lastWake = now;
}
