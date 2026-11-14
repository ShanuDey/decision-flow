// Orval mutator: the browser uses the same-origin /backend proxy; server components call the API directly.

const PROXY_PREFIX = "/backend";
const NO_BODY = [204, 205, 304];

function serverBase(): string {
  const base = process.env.API_URL;
  if (!base) {
    console.error("API_URL is not set: the web server cannot reach the API");
    throw new Error("API_URL is not set");
  }
  return base.replace(/\/+$/, "");
}

function parse(text: string | null): unknown {
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return {};
  }
}

// A notice, not a redirect, so unsaved work stays on the page.
async function notifySessionExpired(): Promise<void> {
  const { toast } = await import("sonner");
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  toast.error("Your session expired.", {
    id: "session-expired",
    duration: Infinity,
    action: { label: "Sign in", onClick: () => window.location.assign(new URL(`/login?next=${next}`, window.location.origin).href) },
  });
}

export async function apiFetch<T>(url: string, options: RequestInit = {}): Promise<T> {
  const target = typeof window === "undefined" ? `${serverBase()}${url}` : `${PROXY_PREFIX}${url}`;
  const response = await fetch(target, options);
  const text = NO_BODY.includes(response.status) ? null : await response.text();
  const data = parse(text);
  // Only the web proxy says "session_expired"; a 401 from the API means its token check failed instead.
  if (typeof window !== "undefined" && (data as { code?: string }).code === "session_expired") {
    void notifySessionExpired();
  }
  return { data, status: response.status, headers: response.headers } as T;
}
