import { after } from "next/server";

import { getConfig } from "@/lib/auth/server";
import { API_TIMEOUT_MS } from "@/lib/backend-proxy";

export const maxDuration = 60;

export const MIN_GAP_MS = 20_000;
let lastWake = 0;

// Public: the sign-in page wakes the API through it. Answers first so no function stays open.
export function GET(): Response {
  const now = Date.now();
  if (now - lastWake >= MIN_GAP_MS) {
    lastWake = now;
    after(async () => {
      try {
        await fetch(`${getConfig().apiUrl}/health`, {
          cache: "no-store",
          signal: AbortSignal.timeout(API_TIMEOUT_MS),
        });
      } catch {
        // Best effort; the page that needs the API reports its own failure.
      }
    });
  }
  return new Response(null, { status: 204 });
}
