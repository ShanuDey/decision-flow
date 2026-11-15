import { beforeEach, describe, expect, it, vi } from "vitest";

// The server module reads env on first use; the helpers never touch it, and authenticateKey gets fakes.
const verifyApiKey = vi.fn();
const query = vi.fn();
vi.mock("./server", () => ({
  getAuth: () => ({ api: { verifyApiKey } }),
  getRuntime: () => ({ pool: { query } }),
}));

import {
  authenticateKey,
  bearerKey,
  failureResponse,
  judge,
  requireAction,
  type VerifyResult,
} from "./api-key";

const KEY = `df_live_${"a".repeat(64)}`;
const headers = (authorization?: string) =>
  new Headers(authorization === undefined ? {} : { authorization });

const valid = (flows: string[]): VerifyResult => ({
  valid: true,
  error: null,
  key: { referenceId: "user-1", permissions: { flows } },
});
const invalid = (code: string, details?: unknown): VerifyResult => ({
  valid: false,
  error: { code, details },
  key: null,
});

describe("bearerKey", () => {
  it("returns a well-formed key", () => {
    expect(bearerKey(headers(`Bearer ${KEY}`))).toBe(KEY);
    expect(bearerKey(headers(`bearer ${KEY}`))).toBe(KEY);
  });

  it.each([
    ["no header", undefined],
    ["wrong scheme", `Basic ${KEY}`],
    ["a JWT", "Bearer aaa.bbb.ccc"],
    ["wrong prefix", `Bearer sk_live_${"a".repeat(64)}`],
    ["extra words", `Bearer ${KEY} extra`],
    ["no token", "Bearer "],
    ["oversized", `Bearer df_live_${"a".repeat(400)}`],
  ])("refuses %s", (_label, value) => {
    expect(bearerKey(headers(value))).toBeNull();
  });
});

describe("judge", () => {
  it("returns the owner and the actions the key holds, in canonical order", () => {
    expect(judge(valid(["run", "read"]))).toEqual({
      ok: true,
      userId: "user-1",
      actions: ["read", "run"],
    });
  });

  it("gives a key with no permissions no actions", () => {
    expect(judge({ valid: true, error: null, key: { referenceId: "u" } })).toEqual({
      ok: true,
      userId: "u",
      actions: [],
    });
  });

  it.each([
    ["KEY_NOT_FOUND", "invalid_key"],
    ["INVALID_API_KEY", "invalid_key"],
    ["SOMETHING_NEW", "invalid_key"],
    ["KEY_EXPIRED", "key_expired"],
    ["KEY_DISABLED", "key_revoked"],
  ])("maps %s to 401 %s", (plugin, code) => {
    expect(judge(invalid(plugin))).toMatchObject({ ok: false, status: 401, code });
  });

  it("treats a valid result without a key as invalid", () => {
    expect(judge({ valid: true, error: null, key: null })).toMatchObject({
      status: 401,
      code: "invalid_key",
    });
  });

  it("maps rate limiting to 429 and rounds tryAgainIn up to seconds", () => {
    expect(judge(invalid("RATE_LIMITED", { tryAgainIn: 2500 }))).toMatchObject({
      status: 429,
      code: "rate_limited",
      retryAfter: 3,
    });
  });

  it("falls back to 60 seconds when the wait is unknown", () => {
    expect(judge(invalid("RATE_LIMITED"))).toMatchObject({ retryAfter: 60 });
    expect(judge(invalid("RATE_LIMITED", { tryAgainIn: "soon" }))).toMatchObject({
      retryAfter: 60,
    });
  });
});

describe("requireAction", () => {
  it("allows an action the key holds", () => {
    expect(requireAction(["read", "run"], "run")).toBeNull();
  });

  it("refuses a missing action with 403 and does not treat write as read", () => {
    expect(requireAction(["write"], "read")).toMatchObject({
      ok: false,
      status: 403,
      code: "insufficient_scope",
      message: 'This key does not have the "read" scope',
    });
    expect(requireAction([], "run")).toMatchObject({ status: 403 });
  });
});

describe("authenticateKey", () => {
  beforeEach(() => {
    verifyApiKey.mockReset();
    query.mockReset();
  });

  it("verifies once and returns the user and the key's actions", async () => {
    verifyApiKey.mockResolvedValue(valid(["read", "write"]));
    query.mockResolvedValue({ rows: [{ id: "user-1", email: "a@acme.com", name: "Alex" }] });

    const result = await authenticateKey(headers(`Bearer ${KEY}`));

    expect(result).toEqual({
      ok: true,
      user: { id: "user-1", email: "a@acme.com", name: "Alex" },
      actions: ["read", "write"],
    });
    expect(verifyApiKey).toHaveBeenCalledTimes(1);
    expect(verifyApiKey).toHaveBeenCalledWith({ body: { key: KEY } });
  });

  it("does not look anything up without a key", async () => {
    expect(await authenticateKey(headers())).toMatchObject({ ok: false, status: 401, code: "missing_key" });
    expect(await authenticateKey(headers("Bearer aaa.bbb.ccc"))).toMatchObject({ code: "missing_key" });
    expect(verifyApiKey).not.toHaveBeenCalled();
  });

  it("passes a plugin refusal through", async () => {
    verifyApiKey.mockResolvedValue(invalid("KEY_EXPIRED"));
    expect(await authenticateKey(headers(`Bearer ${KEY}`))).toMatchObject({ code: "key_expired" });
    expect(query).not.toHaveBeenCalled();
  });

  it("refuses a key whose owner no longer exists", async () => {
    verifyApiKey.mockResolvedValue(valid(["read"]));
    query.mockResolvedValue({ rows: [] });
    expect(await authenticateKey(headers(`Bearer ${KEY}`))).toMatchObject({ status: 401, code: "invalid_key" });
  });
});

describe("failureResponse", () => {
  it("challenges a 401 and never caches", async () => {
    const response = failureResponse({ ok: false, status: 401, code: "invalid_key", message: "Invalid API key" });
    expect(response.status).toBe(401);
    expect(response.headers.get("www-authenticate")).toBe("Bearer");
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(await response.json()).toEqual({ code: "invalid_key", message: "Invalid API key", details: {} });
  });

  it("adds Retry-After on a 429 and no challenge", () => {
    const response = failureResponse({ ok: false, status: 429, code: "rate_limited", message: "x", retryAfter: 7 });
    expect(response.headers.get("retry-after")).toBe("7");
    expect(response.headers.get("www-authenticate")).toBeNull();
  });
});
