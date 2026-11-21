import { describe, expect, it } from "vitest";

import { type CatalogItem, filterItems, groupItems } from "./catalog";

const item = (id: string, group: string, over: Partial<CatalogItem> = {}): CatalogItem => ({
  id,
  name: id,
  description: "",
  icon: "plug",
  docsUrl: "",
  group,
  tags: [],
  ...over,
});

describe("filterItems", () => {
  const items = [
    item("github", "Built-in", { name: "GitHub: create issue", tags: ["issues"] }),
    item("slack", "Built-in", { name: "Slack: post message", description: "Posts to a channel" }),
  ];

  it("returns everything for a blank query", () => {
    expect(filterItems(items, "  ")).toHaveLength(2);
  });

  it("matches name, description and tags, ignoring case and padding", () => {
    expect(filterItems(items, " GITHUB ").map((i) => i.id)).toEqual(["github"]);
    expect(filterItems(items, "channel").map((i) => i.id)).toEqual(["slack"]);
    expect(filterItems(items, "issues").map((i) => i.id)).toEqual(["github"]);
    expect(filterItems(items, "zzz")).toEqual([]);
  });
});

describe("groupItems", () => {
  it("keeps the given order and drops empty groups", () => {
    const items = [item("a", "Custom"), item("b", "Built-in"), item("c", "Custom")];
    const sections = groupItems(items, ["Built-in", "Installed", "Custom"]);
    expect(sections.map((s) => [s.label, s.items.map((i) => i.id)])).toEqual([
      ["Built-in", ["b"]],
      ["Custom", ["a", "c"]],
    ]);
  });
});
