import { describe, expect, it } from "vitest";

import type { NodeTemplate, NodeTemplateItem } from "@/lib/api/models";
import type { ConnectionOption } from "@/lib/connections";

import { applyTemplate, BUILT_IN, connectionNeed, INSTALLED, isBlank, templateItems } from "./node-templates";
import { defaultData } from "./nodes";
import type { HttpRequestData } from "./types";

const template = (over: Partial<NodeTemplate> = {}): NodeTemplate => ({
  id: "github_create_issue",
  name: "GitHub: create issue",
  description: "Opens an issue.",
  node_type: "http_request",
  tags: ["github"],
  connection: { type: "bearer", values: { hosts: "api.github.com" } },
  data: {
    method: "POST",
    url: "https://api.github.com/repos/OWNER/REPO/issues",
    headers: { Accept: "application/vnd.github+json" },
    body_type: "json",
    body: { title: "{{ input.title }}" },
    connection_id: "",
  },
  ...over,
});

const option = (id: string, typeId: string, hosts = "api.github.com"): ConnectionOption => ({
  id,
  name: id,
  typeId,
  typeName: typeId,
  hosts,
});

const blank = (): HttpRequestData => defaultData("http_request");

describe("templateItems", () => {
  const item = (source: NodeTemplateItem["source"], over: Partial<NodeTemplate> = {}): NodeTemplateItem => ({
    source,
    template: template(over),
  });

  it("puts installed templates in their own group", () => {
    const groups = templateItems([item("builtin"), item("installed", { id: "x" })]).map((i) => i.group);
    expect(groups).toEqual([BUILT_IN, INSTALLED]);
  });

  it("turns templates into gallery items, with defaults for the optional parts", () => {
    const [item] = templateItems([{ source: "builtin", template: template() }]);
    expect(item).toEqual({
      id: "github_create_issue",
      name: "GitHub: create issue",
      description: "Opens an issue.",
      icon: "plug",
      docsUrl: "",
      group: BUILT_IN,
      tags: ["github"],
    });
  });
});

describe("connectionNeed", () => {
  it("needs nothing when the template has no connection", () => {
    expect(connectionNeed(template({ connection: null }), [option("a", "bearer")])).toEqual({ kind: "none" });
  });

  it("reports a missing connection type", () => {
    expect(connectionNeed(template(), [option("a", "basic")])).toEqual({ kind: "missing", typeId: "bearer" });
  });

  it("picks the only connection that fits, and asks when several do", () => {
    expect(connectionNeed(template(), [option("a", "bearer"), option("b", "basic")])).toMatchObject({
      kind: "picked",
      connection: { id: "a" },
    });
    expect(connectionNeed(template(), [option("a", "bearer"), option("b", "bearer")])).toMatchObject({
      kind: "choose",
    });
  });

  it("ignores a connection of the right type that does not allow the template's host", () => {
    const other = option("a", "bearer", "api.example.com");
    expect(connectionNeed(template(), [other])).toEqual({ kind: "blocked", typeName: "bearer", host: "api.github.com" });
    expect(connectionNeed(template(), [other, option("b", "bearer")])).toMatchObject({
      kind: "picked",
      connection: { id: "b" },
    });
  });

  it("accepts a wildcard host", () => {
    expect(connectionNeed(template(), [option("a", "bearer", "*.github.com")])).toMatchObject({ kind: "picked" });
  });

  it("cannot judge the host when the URL starts with a placeholder, so it does not block", () => {
    const placeholder = template({ data: { ...template().data, url: "https://{{ input.host }}/x" } });
    expect(connectionNeed(placeholder, [option("a", "bearer", "api.example.com")])).toMatchObject({
      kind: "picked",
    });
  });
});

describe("isBlank", () => {
  it("is true for a fresh node, even with a connection chosen", () => {
    expect(isBlank(blank())).toBe(true);
    expect(isBlank({ ...blank(), connection_id: "c1" })).toBe(true);
  });

  it("does not depend on the order of the keys", () => {
    const reordered = Object.fromEntries(Object.entries(blank()).reverse()) as unknown as HttpRequestData;
    expect(isBlank(reordered)).toBe(true);
  });

  it("is false once anything else is set", () => {
    expect(isBlank({ ...blank(), url: "https://a.com" })).toBe(false);
    expect(isBlank({ ...blank(), headers: { A: "b" } })).toBe(false);
    expect(isBlank({ ...blank(), body: { a: [1] } })).toBe(false);
    expect(isBlank({ ...blank(), fail_on_error_status: true })).toBe(false);
  });
});

describe("applyTemplate", () => {
  it("replaces the settings, starting from the node defaults", () => {
    const current = { ...blank(), url: "https://old.test", query: { a: "1" }, timeout_seconds: 5 };
    const next = applyTemplate(template(), [], current);
    expect(next).toMatchObject({
      method: "POST",
      url: "https://api.github.com/repos/OWNER/REPO/issues",
      query: {},
      timeout_seconds: null,
      body_type: "json",
      body: { title: "{{ input.title }}" },
    });
  });

  it("picks the only connection that fits", () => {
    expect(applyTemplate(template(), [option("a", "bearer")], blank()).connection_id).toBe("a");
  });

  it("keeps the node's own connection when it is one of several that fit", () => {
    const both = [option("a", "bearer"), option("b", "bearer")];
    expect(applyTemplate(template(), both, { ...blank(), connection_id: "b" }).connection_id).toBe("b");
    expect(applyTemplate(template(), both, blank()).connection_id).toBe("");
  });

  it("drops a connection that is the wrong type or does not allow the host", () => {
    const wrongType = option("x", "basic");
    const wrongHost = option("y", "bearer", "api.example.com");
    expect(applyTemplate(template(), [wrongType], { ...blank(), connection_id: "x" }).connection_id).toBe("");
    expect(applyTemplate(template(), [wrongHost], { ...blank(), connection_id: "y" }).connection_id).toBe("");
    expect(applyTemplate(template(), [], { ...blank(), connection_id: "gone" }).connection_id).toBe("");
  });

  it("drops a connection the template does not use", () => {
    const current = { ...blank(), connection_id: "mine" };
    expect(applyTemplate(template({ connection: null }), [], current).connection_id).toBe("");
  });

  it("does not share objects with the template, so editing the node cannot change it", () => {
    const source = template();
    const next = applyTemplate(source, [], blank());
    (next.headers as Record<string, string>).Extra = "x";
    expect(source.data.headers).toEqual({ Accept: "application/vnd.github+json" });
  });
});
