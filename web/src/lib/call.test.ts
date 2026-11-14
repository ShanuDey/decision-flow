import { describe, expect, it } from "vitest";

import { call } from "./call";

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
