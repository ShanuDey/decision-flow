import { describe, expect, it } from "vitest";

import type { AppConfig } from "@/lib/api/models";

import { atLimit, limitsOf, NO_LIMITS, nearLimit } from "./limits";
import { flatTypes, pickerGroups } from "./picker";

const config: AppConfig = {
  delete_mode: "soft",
  disabled_node_types: ["http_request"],
  max_nodes: 50,
  max_edges: 0,
  limit_notice: "Free demo",
  limit_notice_url: "https://example.com/plans",
};

describe("atLimit and nearLimit", () => {
  it("never limit when the maximum is 0", () => {
    expect(atLimit(10_000, 0)).toBe(false);
    expect(nearLimit(10_000, 0)).toBe(false);
  });

  it("is at the limit from the maximum on", () => {
    expect(atLimit(49, 50)).toBe(false);
    expect(atLimit(50, 50)).toBe(true);
  });

  it("is near the limit from 80% on", () => {
    expect(nearLimit(39, 50)).toBe(false);
    expect(nearLimit(40, 50)).toBe(true);
    expect(nearLimit(4, 5)).toBe(true);
  });
});

describe("limitsOf", () => {
  it("maps the server's config", () => {
    expect(limitsOf(config)).toEqual({
      disabledNodeTypes: ["http_request"],
      maxNodes: 50,
      maxEdges: 0,
      notice: { text: "Free demo", url: "https://example.com/plans" },
    });
  });

  it("drops a notice link that is not http(s), and an empty notice", () => {
    expect(limitsOf({ ...config, limit_notice_url: "javascript:alert(1)" }).notice).toEqual({ text: "Free demo" });
    expect(limitsOf({ ...config, limit_notice: "", limit_notice_url: "" }).notice).toBeNull();
  });

  it("has no limits before the server answers", () => {
    expect(NO_LIMITS).toEqual({ disabledNodeTypes: [], maxNodes: 0, maxEdges: 0, notice: null });
  });
});

describe("pickerGroups with turned-off nodes", () => {
  it("hides the types the server refuses", () => {
    const types = flatTypes(pickerGroups("", "all", ["http_request", "subflow"]));
    expect(types).not.toContain("http_request");
    expect(types).not.toContain("subflow");
    expect(types).toContain("assign");
  });

  it("hides nothing by default", () => {
    expect(flatTypes(pickerGroups("", "all"))).toContain("http_request");
  });
});
