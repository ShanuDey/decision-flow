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
