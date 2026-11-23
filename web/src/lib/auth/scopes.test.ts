import { describe, expect, it } from "vitest";

import { FULL_ACCESS, GATEWAY_ROUTES, hasAction, permissionsFor, requiredAction } from "./scopes";

describe("permissionsFor", () => {
  it("groups by resource in canonical order and drops duplicates", () => {
    expect(permissionsFor(["flows:run", "flows:read", "flows:read"])).toEqual({ flows: ["read", "run"] });
    expect(permissionsFor(["agents:manage", "flows:read", "agents:chat"])).toEqual({
      flows: ["read"],
      agents: ["chat", "manage"],
    });
  });

  it("leaves out resources with no action", () => {
    expect(permissionsFor(["flows:read"])).toEqual({ flows: ["read"] });
  });

  it("full access holds every action", () => {
    expect(FULL_ACCESS).toEqual({
      flows: ["read", "write", "run"],
      agents: ["read", "chat", "manage"],
    });
  });
});

describe("hasAction", () => {
  it("does not treat write as read", () => {
    const writeOnly = permissionsFor(["flows:write"]);
    expect(hasAction(writeOnly, "flows:write")).toBe(true);
    expect(hasAction(writeOnly, "flows:read")).toBe(false);
  });

  it("keeps flows and agents apart", () => {
    const flowsOnly = permissionsFor(["flows:read", "flows:write", "flows:run"]);
    expect(hasAction(flowsOnly, "agents:read")).toBe(false);
    const chatOnly = permissionsFor(["agents:chat"]);
    expect(hasAction(chatOnly, "agents:chat")).toBe(true);
    expect(hasAction(chatOnly, "agents:manage")).toBe(false);
    expect(hasAction(chatOnly, "flows:read")).toBe(false);
  });

  it("refuses when permissions are missing", () => {
    expect(hasAction(null, "flows:read")).toBe(false);
    expect(hasAction(undefined, "flows:run")).toBe(false);
    expect(hasAction({}, "flows:read")).toBe(false);
  });
});

describe("requiredAction", () => {
  it.each([
    ["GET", "/flows", "flows:read"],
    ["GET", "/flow-format", "flows:read"],
    ["GET", "/flows/abc", "flows:read"],
    ["GET", "/flows/abc/versions/3", "flows:read"],
    ["POST", "/flows/abc/validate", "flows:read"],
    ["GET", "/runs/abc/steps", "flows:read"],
    ["POST", "/flows", "flows:write"],
    ["PATCH", "/flows/abc", "flows:write"],
    ["DELETE", "/flows/abc", "flows:write"],
    ["PUT", "/flows/abc/draft", "flows:write"],
    ["POST", "/flows/abc/publish", "flows:write"],
    ["POST", "/flows/abc/runs", "flows:run"],
    ["POST", "/flows/abc/trigger", "flows:run"],
    ["GET", "/agents", "agents:read"],
    ["GET", "/agents/abc", "agents:read"],
    ["GET", "/agents/abc/threads", "agents:read"],
    ["GET", "/agents/abc/threads/def", "agents:read"],
    ["GET", "/agents/abc/threads/def/messages/ghi/steps", "agents:read"],
    ["POST", "/agents/abc/threads", "agents:chat"],
    ["DELETE", "/agents/abc/threads/def", "agents:chat"],
    ["POST", "/agents/abc/threads/def/messages", "agents:chat"],
    ["POST", "/agents/abc/invoke", "agents:chat"],
    ["POST", "/agents", "agents:manage"],
    ["PATCH", "/agents/abc", "agents:manage"],
    ["DELETE", "/agents/abc", "agents:manage"],
  ])("%s %s needs %s", (method, path, action) => {
    expect(requiredAction(method, path)).toBe(action);
  });

  it("matches the method case-insensitively", () => {
    expect(requiredAction("get", "/flows")).toBe("flows:read");
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
    ["GET", "/secrets"],
    ["PUT", "/secrets/API_KEY"],
    ["DELETE", "/secrets/API_KEY"],
    ["GET", "/agents/abc/invoke"],
    ["PUT", "/agents/abc"],
    ["POST", "/agents/abc/threads/def/messages/stream"],
    ["GET", "/agents/abc/threads/def/messages"],
    ["DELETE", "/agents/abc/threads"],
  ])("refuses %s %s", (method, path) => {
    expect(requiredAction(method, path)).toBeNull();
  });

  it("gives no two routes the same method and path", () => {
    const keys = GATEWAY_ROUTES.map((r) => `${r.method} ${r.template}`);
    expect(new Set(keys).size).toBe(keys.length);
  });
});
