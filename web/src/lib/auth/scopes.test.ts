import { describe, expect, it } from "vitest";

import { ACTIONS, FULL_ACCESS, hasAction, permissionsFor, requiredAction } from "./scopes";

describe("permissionsFor", () => {
  it("keeps the canonical order and drops duplicates", () => {
    expect(permissionsFor(["run", "read", "read"])).toEqual({ flows: ["read", "run"] });
  });

  it("full access holds every action", () => {
    expect(FULL_ACCESS).toEqual({ flows: [...ACTIONS] });
  });
});

describe("hasAction", () => {
  it("does not treat write as read", () => {
    const writeOnly = permissionsFor(["write"]);
    expect(hasAction(writeOnly, "write")).toBe(true);
    expect(hasAction(writeOnly, "read")).toBe(false);
  });

  it("refuses when permissions are missing", () => {
    expect(hasAction(null, "read")).toBe(false);
    expect(hasAction(undefined, "run")).toBe(false);
    expect(hasAction({}, "read")).toBe(false);
  });
});

describe("requiredAction", () => {
  it.each([
    ["GET", "/flows", "read"],
    ["GET", "/flow-format", "read"],
    ["GET", "/flows/abc", "read"],
    ["GET", "/flows/abc/versions/3", "read"],
    ["POST", "/flows/abc/validate", "read"],
    ["GET", "/runs/abc/steps", "read"],
    ["POST", "/flows", "write"],
    ["PATCH", "/flows/abc", "write"],
    ["DELETE", "/flows/abc", "write"],
    ["PUT", "/flows/abc/draft", "write"],
    ["POST", "/flows/abc/publish", "write"],
    ["POST", "/flows/abc/runs", "run"],
    ["POST", "/flows/abc/trigger", "run"],
  ])("%s %s needs %s", (method, path, action) => {
    expect(requiredAction(method, path)).toBe(action);
  });

  it("matches the method case-insensitively", () => {
    expect(requiredAction("get", "/flows")).toBe("read");
  });

  it.each([
    ["GET", "/me"],
    ["GET", "/flows/abc/extra"],
    ["GET", "/flows/abc/versions/x"],
    ["DELETE", "/runs/abc"],
    ["POST", "/flows/abc/runs/extra"],
    ["GET", "/flows/abc/trigger"],
    ["GET", "/flows/"],
    ["GET", "/templates"],
  ])("refuses %s %s", (method, path) => {
    expect(requiredAction(method, path)).toBeNull();
  });
});
