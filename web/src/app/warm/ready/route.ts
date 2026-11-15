import { getConfig } from "@/lib/auth/server";

export const READY_TIMEOUT_MS = 10_000;

// Public, like /warm: the client polls it to learn when the API is awake.
export async function GET(): Promise<Response> {
  try {
    const res = await fetch(`${getConfig().apiUrl}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(READY_TIMEOUT_MS),
    });
    return new Response(null, { status: res.ok ? 204 : 503 });
  } catch {
    return new Response(null, { status: 503 });
  }
}
