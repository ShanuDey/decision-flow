const FALLBACK = "/flows";
const BASE = "http://local.invalid";

// Only same-site paths may be used as the post-login destination (no open redirect, no login loop).
export function safeNext(value: string | string[] | null | undefined, fallback = FALLBACK): string {
  const candidate = Array.isArray(value) ? value[0] : value;
  if (!candidate || !candidate.startsWith("/") || candidate.startsWith("//")) return fallback;
  if (/[\\\u0000-\u001f]/.test(candidate)) return fallback;
  try {
    const url = new URL(candidate, BASE);
    if (url.origin !== BASE) return fallback;
    if (/^\/(login|api\/auth)(\/|$)/.test(url.pathname)) return fallback;
    return url.pathname + url.search;
  } catch {
    return fallback;
  }
}
