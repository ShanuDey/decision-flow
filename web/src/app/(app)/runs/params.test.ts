import { describe, expect, it } from "vitest";

import { newerHref, olderHref, parseRunsQuery, runsHref, testParam } from "./params";

describe("parseRunsQuery", () => {
  it("reads valid filters and cursors", () => {
    expect(
      parseRunsQuery({ flow: "f1", status: "failed", type: "test", cursor: "c2", back: "c1,c0" }),
    ).toEqual({ flow: "f1", status: "failed", type: "test", cursor: "c2", back: ["c1", "c0"] });
  });

  it("ignores invalid values and takes the first of repeated params", () => {
    const q = parseRunsQuery({ status: "running", type: ["live", "test"], flow: "" });
    expect(q).toEqual({
      flow: undefined,
      status: undefined,
      type: "live",
      cursor: undefined,
      back: [],
    });
  });
});

describe("testParam", () => {
  it("maps type to the API flag", () => {
    expect(testParam("test")).toBe(true);
    expect(testParam("live")).toBe(false);
    expect(testParam(undefined)).toBeUndefined();
  });
});

describe("runsHref", () => {
  it("omits empty params", () => {
    expect(runsHref({})).toBe("/runs");
    expect(runsHref({ status: "failed" })).toBe("/runs?status=failed");
  });
});

describe("paging", () => {
  it("walks older then newer back to the first page", () => {
    const first = parseRunsQuery({});
    expect(newerHref(first)).toBeNull();

    const second = parseRunsQuery(urlParams(olderHref(first, "c1")));
    expect(second).toMatchObject({ cursor: "c1", back: [] });

    const third = parseRunsQuery(urlParams(olderHref(second, "c2")));
    expect(third).toMatchObject({ cursor: "c2", back: ["c1"] });

    const backToSecond = parseRunsQuery(urlParams(newerHref(third)!));
    expect(backToSecond).toMatchObject({ cursor: "c1", back: [] });

    expect(newerHref(backToSecond)).toBe("/runs");
  });

  it("goes to the first page when the back stack is empty or stale", () => {
    expect(newerHref(parseRunsQuery({ cursor: "c1", status: "failed" }))).toBe("/runs?status=failed");
    expect(newerHref(parseRunsQuery({ cursor: "c3", back: "c1,c2" }))).toBe("/runs?cursor=c2&back=c1");
  });

  it("keeps filters while paging", () => {
    const q = parseRunsQuery({ flow: "f1", status: "failed" });
    expect(olderHref(q, "c1")).toBe("/runs?flow=f1&status=failed&cursor=c1");
  });
});

function urlParams(href: string): Record<string, string> {
  return Object.fromEntries(new URL(href, "http://x").searchParams);
}
