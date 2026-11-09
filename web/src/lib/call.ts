// Hand-written wrapper around the generated client (src/lib/api is wiped on every
// regeneration, so this lives one level up). Collapses `{status, data}` unions into ok | error.

export interface ApiFailure {
  status: number; // 0 = network error
  code: string;
  message: string;
  details: Record<string, unknown>;
}

export type ApiResult<T> =
  | { ok: true; status: number; data: T }
  | { ok: false; error: ApiFailure };

type Response = { status: number; data: unknown };
type Success<R extends Response> = Extract<R, { status: 200 | 201 | 202 }>["data"];

function failure(status: number, data: unknown): ApiFailure {
  const body = (data ?? {}) as Record<string, unknown>;
  if (typeof body.code === "string" && typeof body.message === "string") {
    return {
      status,
      code: body.code,
      message: body.message,
      details: (body.details as Record<string, unknown>) ?? {},
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
  return { ok: false, error: failure(res.status, res.data) };
}

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
