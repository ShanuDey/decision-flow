// Hand-written wrapper around the generated client (src/lib/api is wiped on every
// regeneration, so this lives one level up). Collapses `{status, data}` unions into ok | error.

export interface ApiFailure {
  status: number; // 0 = network error
  code: string;
  message: string;
  details: Record<string, unknown>;
  // Seconds from the Retry-After header, when the API sent one.
  retryAfter?: number;
}

export type ApiResult<T> =
  | { ok: true; status: number; data: T }
  | { ok: false; error: ApiFailure };

type Response = { status: number; data: unknown; headers?: Headers };
type Success<R extends Response> = Extract<R, { status: 200 | 201 | 202 }>["data"];

const TOKEN_REJECTED =
  "The API rejected the web server's sign-in token. Check that AUTH_PROVIDERS matches BETTER_AUTH_URL and AUTH_TOKEN_AUDIENCE.";

function failure(status: number, data: unknown, retryAfter?: number): ApiFailure {
  const body = (data ?? {}) as Record<string, unknown>;
  // The web proxy answers a missing session with "session_expired"; "unauthenticated" comes from the API.
  if (status === 401 && body.code === "unauthenticated") {
    return { status, code: body.code, message: TOKEN_REJECTED, details: {} };
  }
  if (typeof body.code === "string" && typeof body.message === "string") {
    return {
      status,
      code: body.code,
      message: body.message,
      details: (body.details as Record<string, unknown>) ?? {},
      ...(retryAfter !== undefined && { retryAfter }),
    };
  }
  return { status, code: "http_error", message: `Request failed (${status})`, details: {} };
}

export async function call<R extends Response>(request: Promise<R>): Promise<ApiResult<Success<R>>> {
  let res: R;
  try {
    res = await request;
  } catch {
    return {
      ok: false,
      error: { status: 0, code: "network_error", message: "Cannot reach the API", details: {} },
    };
  }
  if (res.status >= 200 && res.status < 300) {
    return { ok: true, status: res.status, data: res.data as Success<R> };
  }
  const header = Number(res.headers?.get("retry-after"));
  return {
    ok: false,
    error: failure(res.status, res.data, Number.isFinite(header) && header > 0 ? header : undefined),
  };
}

// A gateway answers 502-504 while the API starts; the API's own 503s carry a code.
const GATEWAY_CODES = ["http_error", "upstream_unavailable"];

export function isUnreachable(error: ApiFailure): boolean {
  if (error.status === 0) return true;
  return [502, 503, 504].includes(error.status) && GATEWAY_CODES.includes(error.code);
}

export const UNREACHABLE_MESSAGE =
  "The server is starting up (the free plan sleeps when idle). Try again in a few seconds.";

export interface FieldIssue {
  code: string;
  message: string;
  node_id: string | null;
  field: string | null;
}

// 422 invalid_flow carries details.errors = [{code, message, node_id, field}]
export function issuesOf(error: ApiFailure): FieldIssue[] {
  const list = error.details.errors;
  if (!Array.isArray(list)) return [];
  return list.map((e) => ({
    code: String(e.code ?? ""),
    message: String(e.message ?? ""),
    node_id: typeof e.node_id === "string" ? e.node_id : null,
    field: typeof e.field === "string" ? e.field : null,
  }));
}

const seconds = (n: number) => `${n} ${n === 1 ? "second" : "seconds"}`;

function retryText(error: ApiFailure): string {
  const raw = error.retryAfter ?? Number(error.details.retry_after);
  const wait = Number.isFinite(raw) && raw > 0 ? Math.ceil(raw) : 0;
  return wait ? `Try again in ${seconds(wait)}.` : "Try again in a few seconds.";
}

// Limit errors get friendly wording; everything else keeps the API's message.
export function errorText(error: ApiFailure): string {
  if (error.code === "rate_limited" && error.details.scope !== "failed_auth") {
    return error.details.scope === "runs"
      ? `You've run this flow a lot just now. ${retryText(error)}`
      : `You're going a bit fast. ${retryText(error)}`;
  }
  if (error.code === "run_limit") {
    return `The server is busy running other flows. ${retryText(error)}`;
  }
  if (error.code === "flow_limit_reached") {
    const limit = Number(error.details.limit);
    const cap = Number.isFinite(limit) && limit > 0 ? `${limit} flows` : "flows";
    return `You have reached the limit of ${cap}. Delete a flow to create a new one.`;
  }
  return error.message;
}

export interface LimitNotice {
  text: string;
  url?: string;
}

// The deployment's optional LIMIT_NOTICE; the link is only kept if it is a plain http(s) URL.
export function noticeOf(error: ApiFailure): LimitNotice | null {
  const text = error.details.notice;
  if (typeof text !== "string" || !text) return null;
  const url = error.details.notice_url;
  return typeof url === "string" && /^https?:\/\//.test(url) ? { text, url } : { text };
}
