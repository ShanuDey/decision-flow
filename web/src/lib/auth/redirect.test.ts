import { describe, expect, it } from "vitest";

import { safeNext } from "./redirect";

describe("safeNext", () => {
  it("keeps a same-site path with its query", () => {
    expect(safeNext("/flows/abc?tab=draft")).toBe("/flows/abc?tab=draft");
    expect(safeNext("/settings/account")).toBe("/settings/account");
  });

  it("falls back when nothing is given", () => {
    expect(safeNext(undefined)).toBe("/flows");
    expect(safeNext(null)).toBe("/flows");
    expect(safeNext("")).toBe("/flows");
  });

  it("uses the first value of a repeated parameter", () => {
    expect(safeNext(["/settings", "/evil"])).toBe("/settings");
  });

  it("rejects other origins and scheme tricks", () => {
    for (const bad of [
      "https://evil.test",
      "//evil.test",
      "/\\evil.test",
      "javascript:alert(1)",
      "flows",
      "/ok\nSet-Cookie: x=1",
    ]) {
      expect(safeNext(bad)).toBe("/flows");
    }
  });

  it("leaves percent-encoded control characters encoded, which is harmless in a path", () => {
    expect(safeNext("/%0d%0aSet-Cookie:%20x=1")).toBe("/%0d%0aSet-Cookie:%20x=1");
  });

  it("never loops back to the login or auth routes", () => {
    expect(safeNext("/login")).toBe("/flows");
    expect(safeNext("/login?next=/x")).toBe("/flows");
    expect(safeNext("/api/auth/sign-out")).toBe("/flows");
  });

  it("honours a custom fallback", () => {
    expect(safeNext("https://evil.test", "/home")).toBe("/home");
  });
});
