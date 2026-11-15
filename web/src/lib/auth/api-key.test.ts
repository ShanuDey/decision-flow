import { describe, expect, it, vi } from "vitest";

// The server module reads env on first use; these helpers never touch it.
vi.mock("./server", () => ({ getAuth: vi.fn(), getRuntime: vi.fn() }));

import { bearerKey, failureResponse, judge, type VerifyResult } from "./api-key";

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
  it("accepts a key that holds the action", () => {
    expect(judge(valid(["read", "run"]), "run")).toEqual({ ok: true, userId: "user-1" });
  });

  it("refuses a missing scope with 403 and does not treat write as read", () => {
    expect(judge(valid(["write"]), "read")).toMatchObject({
      ok: false,
      status: 403,
      code: "insufficient_scope",
    });
    expect(judge({ valid: true, error: null, key: { referenceId: "u" } }, "read")).toMatchObject({
      status: 403,
    });
  });

  it.each([
    ["KEY_NOT_FOUND", "invalid_key"],
    ["INVALID_API_KEY", "invalid_key"],
    ["SOMETHING_NEW", "invalid_key"],
    ["KEY_EXPIRED", "key_expired"],
    ["KEY_DISABLED", "key_revoked"],
  ])("maps %s to 401 %s", (plugin, code) => {
    expect(judge(invalid(plugin), "read")).toMatchObject({ ok: false, status: 401, code });
  });

  it("treats a valid result without a key as invalid", () => {
    expect(judge({ valid: true, error: null, key: null }, "read")).toMatchObject({
      status: 401,
      code: "invalid_key",
    });
  });

  it("maps rate limiting to 429 and rounds tryAgainIn up to seconds", () => {
    expect(judge(invalid("RATE_LIMITED", { tryAgainIn: 2500 }), "read")).toMatchObject({
      status: 429,
      code: "rate_limited",
      retryAfter: 3,
    });
  });

  it("falls back to 60 seconds when the wait is unknown", () => {
    expect(judge(invalid("RATE_LIMITED"), "read")).toMatchObject({ retryAfter: 60 });
    expect(judge(invalid("RATE_LIMITED", { tryAgainIn: "soon" }), "read")).toMatchObject({
      retryAfter: 60,
    });
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
