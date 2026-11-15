import { getConfig } from "@/lib/auth/server";
import { errorResponse } from "@/lib/backend-proxy";

export const READY_TIMEOUT_MS = 15_000;
export const CACHE_MS = 10_000;

let cached: { at: number; status: number; body: string } | null = null;

// Cached: /ready queries the database, so all visitors share one upstream call.
export async function GET(): Promise<Response> {
  const now = Date.now();
  if (!cached || now - cached.at >= CACHE_MS) {
    try {
      const res = await fetch(`${getConfig().apiUrl}/ready`, {
        cache: "no-store",
        signal: AbortSignal.timeout(READY_TIMEOUT_MS),
      });
      const body = await res.text();
      if (res.status !== 200 && res.status !== 503) {
        return errorResponse(502, "upstream_unavailable", "The service is unavailable");
      }
      cached = { at: now, status: res.status, body };
    } catch {
      return errorResponse(502, "upstream_unavailable", "The service is unavailable");
    }
  }
  return new Response(cached.body, {
    status: cached.status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}
