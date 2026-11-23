import { describe, expect, it } from "vitest";

import {
  actionsOf,
  createKeyBody,
  expiresInSeconds,
  expiryDays,
  formatKeyDate,
  keyStatus,
  NAME_MAX,
} from "./key-request";

const valid = { name: "ci", actions: ["flows:run"], expiresInDays: 30 };

describe("createKeyBody", () => {
  it("accepts a valid body and trims the name", () => {
    const parsed = createKeyBody.parse({ ...valid, name: "  ci  " });
    expect(parsed).toEqual({ name: "ci", actions: ["flows:run"], expiresInDays: 30 });
  });

  it("accepts no expiry", () => {
    expect(createKeyBody.safeParse({ ...valid, expiresInDays: null }).success).toBe(true);
  });

  it.each([
    ["blank name", { ...valid, name: "   " }],
    ["name over the limit", { ...valid, name: "x".repeat(NAME_MAX + 1) }],
    ["no actions", { ...valid, actions: [] }],
    ["unknown action", { ...valid, actions: ["admin"] }],
    ["expiry outside the choices", { ...valid, expiresInDays: 7 }],
    ["missing expiry", { name: "ci", actions: ["flows:run"] }],
  ])("rejects %s", (_label, body) => {
    expect(createKeyBody.safeParse(body).success).toBe(false);
  });

  it("accepts a name at the limit", () => {
    expect(createKeyBody.safeParse({ ...valid, name: "x".repeat(NAME_MAX) }).success).toBe(true);
  });
});

describe("expiry", () => {
  it("maps select values to days", () => {
    expect(expiryDays("30")).toBe(30);
    expect(expiryDays("365")).toBe(365);
    expect(expiryDays("never")).toBeNull();
    expect(expiryDays("junk")).toBeNull();
  });

  it("converts days to seconds", () => {
    expect(expiresInSeconds(30)).toBe(2_592_000);
    expect(expiresInSeconds(90)).toBe(7_776_000);
    expect(expiresInSeconds(null)).toBeNull();
  });
});

describe("createKeyBody scopes", () => {
  it("accepts agent scopes and refuses the old unprefixed names", () => {
    const body = { name: "app", expiresInDays: 30 };
    expect(createKeyBody.safeParse({ ...body, actions: ["agents:chat", "agents:read"] }).success).toBe(true);
    expect(createKeyBody.safeParse({ ...body, actions: ["chat"] }).success).toBe(false);
    expect(createKeyBody.safeParse({ ...body, actions: ["run"] }).success).toBe(false);
  });
});

describe("actionsOf", () => {
  it("lists held actions in canonical order", () => {
    expect(actionsOf({ flows: ["run", "read"] })).toEqual(["flows:read", "flows:run"]);
  });

  it("ignores unknown actions and missing permissions", () => {
    expect(actionsOf({ flows: ["admin"] })).toEqual([]);
    expect(actionsOf(null)).toEqual([]);
    expect(actionsOf({})).toEqual([]);
  });

  it("reads agent scopes next to flow scopes", () => {
    expect(actionsOf({ flows: ["read"], agents: ["manage", "chat"] })).toEqual([
      "flows:read",
      "agents:chat",
      "agents:manage",
    ]);
    expect(actionsOf({ agents: ["chat"] })).toEqual(["agents:chat"]);
  });
});

describe("keyStatus", () => {
  const now = new Date("2026-11-15T12:00:00Z");

  it("treats no expiry as active", () => {
    expect(keyStatus(null, now)).toBe("active");
  });

  it("is active before the expiry and expired at or after it", () => {
    expect(keyStatus("2026-11-16T00:00:00Z", now)).toBe("active");
    expect(keyStatus("2026-11-15T12:00:00Z", now)).toBe("expired");
    expect(keyStatus("2026-11-01T00:00:00Z", now)).toBe("expired");
  });
});

describe("formatKeyDate", () => {
  it("formats in UTC", () => {
    expect(formatKeyDate("2026-11-15T23:30:00Z")).toBe("15 Nov 2026");
  });
});
