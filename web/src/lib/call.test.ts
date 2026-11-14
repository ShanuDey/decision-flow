import { describe, expect, it } from "vitest";

import { call, isUnreachable } from "./call";

const respond = (status: number, data: unknown) => Promise.resolve({ status, data });

describe("call: 401 responses", () => {
  it("keeps the web proxy's session_expired as a sign-in problem", async () => {
    const result = await call(
      respond(401, { code: "session_expired", message: "Sign in required", details: {} }),
    );
    expect(result).toMatchObject({ ok: false, error: { code: "session_expired", message: "Sign in required" } });
  });

  it("explains an API token rejection as a configuration problem, not a sign-in one", async () => {
    const result = await call(
      respond(401, { code: "unauthenticated", message: "Invalid or expired token", details: {} }),
    );
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe("unauthenticated");
      expect(result.error.message).toContain("AUTH_PROVIDERS");
      expect(result.error.message).toContain("BETTER_AUTH_URL");
    }
  });

  it("leaves other errors as the API sent them", async () => {
    const result = await call(respond(404, { code: "not_found", message: "No such flow", details: {} }));
    expect(result).toMatchObject({ ok: false, error: { status: 404, message: "No such flow" } });
  });
});

describe("isUnreachable", () => {
  it("is true for a network error and gateway answers, false for the API's own errors", () => {
    const failure = (status: number, code = "http_error") => ({
      status,
      code,
      message: "m",
      details: {},
    });
    for (const status of [0, 502, 503, 504]) expect(isUnreachable(failure(status))).toBe(true);
    expect(isUnreachable(failure(502, "upstream_unavailable"))).toBe(true);
    expect(isUnreachable(failure(503, "auth_unavailable"))).toBe(false);
    for (const status of [400, 401, 404, 422, 429, 500]) {
      expect(isUnreachable(failure(status))).toBe(false);
    }
  });
});

import { errorText, noticeOf } from "./call";
import type { ApiFailure } from "./call";

const fail = (code: string, details: Record<string, unknown> = {}, extra: Partial<ApiFailure> = {}): ApiFailure => ({
  status: 429,
  code,
  message: "raw api message",
  details,
  ...extra,
});

describe("call: Retry-After", () => {
  it("reads the header into retryAfter on a failure", async () => {
    const response = {
      status: 429,
      data: { code: "run_limit", message: "busy", details: {} },
      headers: new Headers({ "Retry-After": "3" }),
    };
    const result = await call(Promise.resolve(response));
    expect(result).toMatchObject({ ok: false, error: { code: "run_limit", retryAfter: 3 } });
  });
});

describe("errorText", () => {
  it("words a per-user or per-IP rate limit with the wait", () => {
    expect(errorText(fail("rate_limited", { scope: "user", retry_after: 12 }))).toBe(
      "You're going a bit fast. Try again in 12 seconds.",
    );
    expect(errorText(fail("rate_limited", { scope: "ip", retry_after: 1 }))).toBe(
      "You're going a bit fast. Try again in 1 second.",
    );
  });

  it("words run limits", () => {
    expect(errorText(fail("rate_limited", { scope: "runs", retry_after: 5 }))).toBe(
      "You've run this flow a lot just now. Try again in 5 seconds.",
    );
    expect(errorText(fail("run_limit", { scope: "app" }, { retryAfter: 3 }))).toBe(
      "The server is busy running other flows. Try again in 3 seconds.",
    );
  });

  it("falls back to a vague wait when no seconds are known", () => {
    expect(errorText(fail("rate_limited", { scope: "user" }))).toBe(
      "You're going a bit fast. Try again in a few seconds.",
    );
  });

  it("explains the flow limit", () => {
    expect(errorText(fail("flow_limit_reached", { limit: 20, count: 20 }, { status: 409 }))).toBe(
      "You have reached the limit of 20 flows. Delete a flow to create a new one.",
    );
  });

  it("leaves sign-in limits and all other errors as the API sent them", () => {
    expect(errorText(fail("rate_limited", { scope: "failed_auth" }))).toBe("raw api message");
    expect(errorText(fail("not_found", {}, { status: 404 }))).toBe("raw api message");
  });
});

describe("noticeOf", () => {
  it("returns the configured notice, and the link only when it is http(s)", () => {
    expect(noticeOf(fail("rate_limited", { notice: "Free demo", notice_url: "https://example.com" }))).toEqual({
      text: "Free demo",
      url: "https://example.com",
    });
    expect(noticeOf(fail("rate_limited", { notice: "Free demo", notice_url: "javascript:alert(1)" }))).toEqual({
      text: "Free demo",
    });
    expect(noticeOf(fail("rate_limited", {}))).toBeNull();
  });
});
