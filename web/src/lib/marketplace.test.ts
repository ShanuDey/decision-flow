import { describe, expect, it } from "vitest";

import type { IndexEntry, InstalledSummary } from "@/lib/api/models";

import { filterEntries, installBody, joinCatalog, relativeTime } from "./marketplace";

const entry = (over: Partial<IndexEntry> & Pick<IndexEntry, "id" | "kind">): IndexEntry => ({
  name: over.id,
  description: "",
  icon: "plug",
  tags: [],
  version: "1.0.0",
  hash: `sha256-${over.id}`,
  path: `${over.kind}/${over.id}/1.0.0.json`,
  requires: [],
  has_readme: false,
  ...over,
});

const installedItem = (kind: InstalledSummary["kind"], id: string, over: Partial<InstalledSummary> = {}): InstalledSummary => ({
  kind,
  id,
  name: id,
  version: "1.0.0",
  hash: `sha256-${id}`,
  installed_at: "2026-11-19T00:00:00",
  ...over,
});

const github = entry({ id: "github", kind: "connection-type", name: "GitHub" });
const issue = entry({
  id: "github_create_issue",
  kind: "node-template",
  name: "GitHub: create issue",
  description: "Opens an issue.",
  tags: ["github", "issues"],
  requires: ["connection-type/github"],
});

describe("joinCatalog", () => {
  it("marks everything available when nothing is installed, and lists what a template needs", () => {
    const [type, template] = joinCatalog([github, issue], []);
    expect([type.status, type.installedVersion, type.alsoInstalls]).toEqual(["available", null, []]);
    expect([template.status, template.alsoInstalls]).toEqual(["available", ["GitHub"]]);
  });

  it("marks an item installed when its hash matches the entry", () => {
    const [type] = joinCatalog([github], [installedItem("connection-type", "github")]);
    expect([type.status, type.installedVersion]).toEqual(["installed", "1.0.0"]);
  });

  it("marks an update when the installed copy differs from the entry", () => {
    const old = installedItem("connection-type", "github", { version: "0.9.0", hash: "sha256-old" });
    const [type] = joinCatalog([github], [old]);
    expect([type.status, type.installedVersion]).toEqual(["update", "0.9.0"]);
  });

  it("does not list a requirement that is already installed", () => {
    const [, template] = joinCatalog([github, issue], [installedItem("connection-type", "github")]);
    expect(template.alsoInstalls).toEqual([]);
  });

  it("keeps a kind and an id apart", () => {
    const same = entry({ id: "github", kind: "node-template" });
    const [, template] = joinCatalog([github, same], [installedItem("connection-type", "github")]);
    expect(template.status).toBe("available");
  });

  it("falls back to the raw key for a requirement the index does not list", () => {
    const lonely = entry({ id: "x", kind: "node-template", requires: ["connection-type/missing"] });
    expect(joinCatalog([lonely], [])[0].alsoInstalls).toEqual(["connection-type/missing"]);
  });
});

describe("filterEntries", () => {
  const all = joinCatalog([github, issue], []);

  it("returns everything for a blank query and no kinds", () => {
    expect(filterEntries(all, { query: "  ", kinds: null })).toHaveLength(2);
  });

  it("filters by kind", () => {
    expect(filterEntries(all, { query: "", kinds: ["connection-type"] }).map((e) => e.id)).toEqual(["github"]);
    expect(filterEntries(all, { query: "", kinds: ["connection-type", "node-template"] })).toHaveLength(2);
  });

  it("matches name, description and tags, ignoring case and padding", () => {
    expect(filterEntries(all, { query: " ISSUES ", kinds: null }).map((e) => e.id)).toEqual(["github_create_issue"]);
    expect(filterEntries(all, { query: "opens", kinds: null })).toHaveLength(1);
    expect(filterEntries(all, { query: "zzz", kinds: null })).toEqual([]);
  });

  it("combines a kind with a search", () => {
    expect(filterEntries(all, { query: "github", kinds: ["node-template"] }).map((e) => e.id)).toEqual([
      "github_create_issue",
    ]);
  });
});

describe("installBody", () => {
  it("sends only what the server checks: kind, id, version and hash", () => {
    const [type] = joinCatalog([github], []);
    expect(installBody(type)).toEqual({
      kind: "connection-type",
      id: "github",
      version: "1.0.0",
      hash: "sha256-github",
    });
  });
});

describe("relativeTime", () => {
  const now = Date.parse("2026-01-01T12:00:00Z");
  it.each([
    ["2026-01-01T11:59:50Z", "just now"],
    ["2026-01-01T11:55:00Z", "5 min ago"],
    ["2026-01-01T09:00:00Z", "3 h ago"],
    ["2025-12-30T12:00:00Z", "2 d ago"],
    ["2026-01-01T12:00:30Z", "just now"],
  ])("%s is %s", (iso, text) => {
    expect(relativeTime(iso, now)).toBe(text);
  });
});
