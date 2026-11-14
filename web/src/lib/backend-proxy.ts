export const PROXY_PREFIX = "/backend";

const REQUEST_HEADERS = ["accept", "accept-language", "content-type", "if-match", "if-none-match"];
const RESPONSE_HEADER_BLOCKLIST = [
  "connection",
  "keep-alive",
  "transfer-encoding",
  "content-encoding",
  "content-length",
  "set-cookie",
  "server",
  "location",
  "www-authenticate",
];
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export function isSafeMethod(method: string): boolean {
  return SAFE_METHODS.has(method.toUpperCase());
}

export function hasBody(method: string): boolean {
  return !["GET", "HEAD"].includes(method.toUpperCase());
}

// Browsers always send Origin on unsafe same-origin requests; anything else is rejected.
export function isAllowedOrigin(
  origin: string | null,
  appUrl: string,
  extraOrigins: string[] = [],
): boolean {
  if (!origin) return false;
  try {
    const actual = new URL(origin).origin;
    return actual === new URL(appUrl).origin || extraOrigins.includes(actual);
  } catch {
    return false;
  }
}

export function upstreamPath(segments: string[]): string | null {
  if (segments.length === 0) return null;
  if (segments.some((s) => s === "" || s === "." || s === ".." || /[/\\]/.test(s))) return null;
  return "/" + segments.map(encodeURIComponent).join("/");
}

export function upstreamHeaders(incoming: Headers, token: string): Headers {
  const out = new Headers();
  for (const name of REQUEST_HEADERS) {
    const value = incoming.get(name);
    if (value !== null) out.set(name, value);
  }
  out.set("authorization", `Bearer ${token}`);
  return out;
}

// Rewrites an upstream redirect to the public prefix; a redirect elsewhere is dropped.
export function publicLocation(location: string | null, apiUrl: string): string | null {
  if (!location) return null;
  try {
    const base = new URL(apiUrl);
    const target = new URL(location, base);
    if (target.origin !== base.origin) return null;
    return `${PROXY_PREFIX}${target.pathname}${target.search}`;
  } catch {
    return null;
  }
}

export function responseHeaders(upstream: Headers, apiUrl: string): Headers {
  const out = new Headers();
  upstream.forEach((value, name) => {
    if (!RESPONSE_HEADER_BLOCKLIST.includes(name.toLowerCase())) out.set(name, value);
  });
  const location = publicLocation(upstream.get("location"), apiUrl);
  if (location) out.set("location", location);
  return out;
}

export function errorResponse(status: number, code: string, message: string): Response {
  return Response.json({ code, message, details: {} }, { status });
}
