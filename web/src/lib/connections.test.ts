import { describe, expect, it } from "vitest";

import type { ConnectionSummary, ConnectionTypeInfo, FieldInfo } from "@/lib/api/models";

import {
  connectionOptions,
  fieldProblem,
  formProblem,
  groupTypes,
  hostsLabel,
  isUrl,
  payloadValues,
  suggestName,
} from "./connections";

const field = (over: Partial<FieldInfo> & Pick<FieldInfo, "name" | "label">): FieldInfo => ({
  secret: false,
  required: true,
  help: "",
  format: "text",
  default: "",
  placeholder: "",
  ...over,
});

const type = (over: Partial<ConnectionTypeInfo> & Pick<ConnectionTypeInfo, "id" | "name" | "fields">) =>
  ({
    description: "",
    icon: "plug",
    docs_url: "",
    category: "custom",
    hosts: [],
    hosts_from: "",
    testable: false,
    ...over,
  }) satisfies ConnectionTypeInfo;

const bearer = type({
  id: "bearer",
  name: "Bearer token",
  fields: [
    field({ name: "token", label: "Token", secret: true }),
    field({ name: "hosts", label: "Allowed hosts" }),
  ],
});

const fixed = type({
  id: "acme",
  name: "Acme",
  category: "builtin",
  hosts: ["api.acme.test"],
  fields: [field({ name: "api_key", label: "API key", secret: true })],
});

const openai = type({
  id: "openai",
  name: "OpenAI",
  category: "builtin",
  hosts_from: "base_url",
  fields: [
    field({ name: "api_key", label: "API key", secret: true }),
    field({ name: "base_url", label: "Base URL", format: "url", default: "https://api.openai.com/v1" }),
  ],
});

const saved = (kind: string, config: Record<string, string>): ConnectionSummary => ({
  id: `${kind}-1`,
  name: "Billing",
  type: kind,
  config,
  secrets_set: [],
  created_at: "",
  updated_at: "",
});

describe("fieldProblem", () => {
  const [token, hosts] = bearer.fields;
  const base = openai.fields[1];

  it("requires a value when creating", () => {
    expect(fieldProblem(token, "", false)).toBe("Token is required");
    expect(fieldProblem(hosts, "  ", false)).toBe("Allowed hosts is required");
  });

  it("lets a secret stay blank when editing, but not a plain field", () => {
    expect(fieldProblem(token, "", true)).toBeNull();
    expect(fieldProblem(hosts, "", true)).toBe("Allowed hosts is required");
  });

  it("holds a secret to the minimum length, wherever it is typed", () => {
    expect(fieldProblem(token, "short", false)).toBe("Token must be at least 8 characters");
    expect(fieldProblem(token, "short", true)).toBe("Token must be at least 8 characters");
    expect(fieldProblem(token, "long-enough", false)).toBeNull();
  });

  it("accepts a blank field that has a default, and checks a URL when one is typed", () => {
    expect(fieldProblem(base, "", false)).toBeNull();
    expect(fieldProblem(base, "api.groq.com", false)).toBe("Base URL must start with http:// or https://");
    expect(fieldProblem(base, "https://api.groq.com/openai/v1", false)).toBeNull();
  });
});

describe("isUrl", () => {
  it.each([
    ["https://a.com/v1", true],
    [" http://localhost:11434/v1 ", true],
    ["a.com", false],
    ["ftp://a.com", false],
    ["https://", false],
    ["", false],
  ])("%s", (value, expected) => {
    expect(isUrl(value)).toBe(expected);
  });
});

describe("formProblem", () => {
  const ok = { token: "long-enough", hosts: "a.com" };

  it("needs a type and a name first", () => {
    expect(formProblem(undefined, "x", ok, false)).toBe("Pick a type");
    expect(formProblem(bearer, "  ", ok, false)).toBe("Enter a name");
  });

  it("reports the first field that cannot be saved", () => {
    expect(formProblem(bearer, "x", { ...ok, token: "" }, false)).toBe("Token is required");
    expect(formProblem(bearer, "x", ok, false)).toBeNull();
  });

  it("lets the OpenAI card be saved with just a key", () => {
    expect(formProblem(openai, "x", { api_key: "sk-long-enough" }, false)).toBeNull();
  });
});

describe("payloadValues", () => {
  it("sends every field when creating, trimming plain ones only", () => {
    expect(payloadValues(bearer, { token: " tok-12345678 ", hosts: " a.com " }, false)).toEqual({
      token: " tok-12345678 ",
      hosts: "a.com",
    });
  });

  it("leaves a blank secret out when editing so the saved one is kept", () => {
    expect(payloadValues(bearer, { token: "", hosts: "b.com" }, true)).toEqual({ hosts: "b.com" });
    expect(payloadValues(bearer, { token: "new-token-123", hosts: "b.com" }, true)).toEqual({
      token: "new-token-123",
      hosts: "b.com",
    });
  });
});

describe("hosts", () => {
  it("shows a fixed type's host, or the host the user listed", () => {
    expect(hostsLabel(saved("acme", {}), fixed)).toBe("api.acme.test");
    expect(hostsLabel(saved("bearer", { hosts: "a.com, b.com" }), bearer)).toBe("a.com, b.com");
  });

  it("takes the host from the base URL, or from its default", () => {
    expect(hostsLabel(saved("openai", { base_url: "https://api.groq.com/openai/v1" }), openai)).toBe("api.groq.com");
    expect(hostsLabel(saved("openai", {}), openai)).toBe("api.openai.com");
  });

  it("builds picker options with the type name and hosts", () => {
    const options = connectionOptions(
      [saved("acme", {}), saved("bearer", { hosts: "a.com" }), saved("gone", {})],
      [fixed, bearer],
    );
    expect(options.map((o) => [o.typeName, o.hosts])).toEqual([
      ["Acme", "api.acme.test"],
      ["Bearer token", "a.com"],
      ["gone", ""],
    ]);
  });
});

describe("groupTypes", () => {
  const all = [openai, fixed, bearer];

  it("splits built-in from custom", () => {
    const { builtin, custom } = groupTypes(all, "");
    expect(builtin.map((t) => t.id)).toEqual(["openai", "acme"]);
    expect(custom.map((t) => t.id)).toEqual(["bearer"]);
  });

  it("filters by name or description, ignoring case and padding", () => {
    expect(groupTypes(all, "  OPEN ").builtin.map((t) => t.id)).toEqual(["openai"]);
    expect(groupTypes(all, "zzz")).toEqual({ builtin: [], custom: [] });
  });
});

describe("suggestName", () => {
  it("offers the type's name", () => {
    expect(suggestName(bearer, {}, [])).toBe("Bearer token");
  });

  it("numbers it when the name is taken, ignoring case and padding", () => {
    expect(suggestName(bearer, {}, ["bearer token "])).toBe("Bearer token 2");
    expect(suggestName(bearer, {}, ["Bearer token", "Bearer token 2"])).toBe("Bearer token 3");
  });

  it("uses the host of a typed base URL for a type that takes one", () => {
    const values = { base_url: "https://api.groq.com/openai/v1" };
    expect(suggestName(openai, values, [])).toBe("api.groq.com");
    expect(suggestName(openai, values, ["api.groq.com"])).toBe("api.groq.com 2");
  });

  it("falls back to the type's name while the URL is blank or not yet valid", () => {
    expect(suggestName(openai, {}, [])).toBe("OpenAI");
    expect(suggestName(openai, { base_url: "https://" }, [])).toBe("OpenAI");
  });

  it("keeps the result within the name limit", () => {
    const long = { ...bearer, name: "x".repeat(200) };
    expect(suggestName(long, {}, [])).toHaveLength(80);
  });
});
