import type { TokenUser } from "./api-token";
import { actionsOf } from "./key-request";
import { type Action, KEY_PREFIX, type Permissions } from "./scopes";
import { getAuth, getRuntime } from "./server";

export interface KeyFailure {
  ok: false;
  status: 401 | 403 | 429;
  code: string;
  message: string;
  retryAfter?: number;
}

export interface KeyIdentity {
  user: TokenUser;
  actions: Action[];
}

export type KeyAuth = ({ ok: true } & KeyIdentity) | KeyFailure;

export interface VerifyResult {
  valid: boolean;
  error: { code?: string; details?: unknown } | null;
  key: { referenceId: string; permissions?: Permissions | null } | null;
}

const MAX_KEY_LENGTH = 256;
const DEFAULT_RETRY_SECONDS = 60;

const fail = (status: KeyFailure["status"], code: string, message: string, retryAfter?: number): KeyFailure => ({
  ok: false,
  status,
  code,
  message,
  ...(retryAfter !== undefined && { retryAfter }),
});

// Only our own keys go to the plugin, so a session token or JWT in the header is never looked up.
export function bearerKey(headers: Headers): string | null {
  const match = /^Bearer\s+(\S+)$/i.exec(headers.get("authorization") ?? "");
  const token = match?.[1];
  return token && token.startsWith(KEY_PREFIX) && token.length <= MAX_KEY_LENGTH ? token : null;
}

function retrySeconds(error: VerifyResult["error"]): number {
  const details = error?.details as { tryAgainIn?: unknown } | undefined;
  const ms = Number(details?.tryAgainIn);
  return Number.isFinite(ms) && ms > 0 ? Math.ceil(ms / 1000) : DEFAULT_RETRY_SECONDS;
}

export function judge(
  result: VerifyResult,
): { ok: true; userId: string; actions: Action[] } | KeyFailure {
  if (!result.valid || !result.key) {
    switch (result.error?.code) {
      case "KEY_EXPIRED":
        return fail(401, "key_expired", "This API key has expired");
      case "KEY_DISABLED":
        return fail(401, "key_revoked", "This API key is disabled");
      case "RATE_LIMITED":
      case "RATE_LIMIT_EXCEEDED":
      case "USAGE_EXCEEDED":
        return fail(429, "rate_limited", "Too many requests with this key", retrySeconds(result.error));
      default:
        return fail(401, "invalid_key", "Invalid API key");
    }
  }
  return { ok: true, userId: result.key.referenceId, actions: actionsOf(result.key.permissions) };
}

export function requireAction(actions: readonly Action[], action: Action): KeyFailure | null {
  return actions.includes(action)
    ? null
    : fail(403, "insufficient_scope", `This key does not have the "${action}" scope`);
}

export function failureResponse(failure: KeyFailure): Response {
  const headers = new Headers({ "cache-control": "no-store" });
  if (failure.status === 401) headers.set("www-authenticate", "Bearer");
  if (failure.retryAfter !== undefined) headers.set("retry-after", String(failure.retryAfter));
  const { code, message } = failure;
  return Response.json({ code, message, details: {} }, { status: failure.status, headers });
}

export async function authenticateKey(headers: Headers): Promise<KeyAuth> {
  const key = bearerKey(headers);
  if (!key) return fail(401, "missing_key", "Send the API key as: Authorization: Bearer <key>");

  // Verified without permissions: the plugin reports a missing permission as an unknown key.
  const verdict = judge(await getAuth().api.verifyApiKey({ body: { key } }));
  if (!verdict.ok) return verdict;

  const { rows } = await getRuntime().pool.query<TokenUser>(
    'select id, email, "emailVerified", name from "user" where id = $1',
    [verdict.userId],
  );
  const user = rows[0];
  return user ? { ok: true, user, actions: verdict.actions } : fail(401, "invalid_key", "Invalid API key");
}
