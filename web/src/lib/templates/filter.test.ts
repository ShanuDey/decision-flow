import { describe, expect, it } from "vitest";

import type { Template } from "@/lib/api/models";

import {
  ALL_CATEGORIES,
  categoriesOf,
  filterTemplates,
  flatTemplates,
  groupByCategory,
} from "./filter";

const make = (id: string, title: string, category: string, summary = ""): Template => ({
  id,
  title,
  summary,
  description: "",
  category,
  inputs: [],
  outputs: [],
  node_types: [],
  draft: {},
});

const items = [
  make("loan", "Loan eligibility", "Decisioning", "Approve or decline"),
  make("lead", "Lead scoring", "Routing", "Route a lead"),
  make("discount", "Discount tier", "Decisioning"),
];

describe("filterTemplates", () => {
  it("returns everything with no query and all categories", () => {
    expect(filterTemplates(items, "", ALL_CATEGORIES)).toHaveLength(3);
  });

  it("matches title and summary, ignoring case and padding", () => {
    expect(filterTemplates(items, "  LEAD ", ALL_CATEGORIES).map((t) => t.id)).toEqual(["lead"]);
    expect(filterTemplates(items, "decline", ALL_CATEGORIES).map((t) => t.id)).toEqual(["loan"]);
  });

  it("filters by category and combines it with the query", () => {
    expect(filterTemplates(items, "", "Decisioning").map((t) => t.id)).toEqual(["loan", "discount"]);
    expect(filterTemplates(items, "lead", "Decisioning")).toEqual([]);
  });
});

describe("grouping", () => {
  it("lists categories once, sorted", () => {
    expect(categoriesOf(items)).toEqual(["Decisioning", "Routing"]);
  });

  it("groups by category and flattens in the same order", () => {
    const groups = groupByCategory(items);
    expect(groups.map((g) => g.category)).toEqual(["Decisioning", "Routing"]);
    expect(flatTemplates(groups).map((t) => t.id)).toEqual(["loan", "discount", "lead"]);
  });
});
