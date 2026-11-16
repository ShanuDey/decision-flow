import { describe, expect, it } from "vitest";

import { NAME_MAX, nameProblem, normalizeName, VALUE_MAX, VALUE_MIN, valueProblem } from "./secrets";

describe("normalizeName", () => {
  it.each([
    ["stripe_key", "STRIPE_KEY"],
    ["Stripe Key", "STRIPE_KEY"],
    ["my-api  key", "MY_API_KEY"],
    ["api.key!", "APIKEY"],
    ["KEY_2", "KEY_2"],
    ["", ""],
  ])("%s -> %s", (raw, expected) => {
    expect(normalizeName(raw)).toBe(expected);
  });

  it("stops at the longest name the API accepts", () => {
    expect(normalizeName("a".repeat(NAME_MAX + 10))).toHaveLength(NAME_MAX);
  });
});

describe("nameProblem", () => {
  it.each(["A", "STRIPE_KEY", "K2", "A".repeat(NAME_MAX)])("accepts %s", (name) => {
    expect(nameProblem(name)).toBeNull();
  });

  it.each([
    ["", "Enter a name"],
    ["1KEY", "Start with a letter"],
    ["_KEY", "Start with a letter"],
  ])("rejects %s", (name, message) => {
    expect(nameProblem(name)).toBe(message);
  });
});

describe("valueProblem", () => {
  it("needs the minimum length", () => {
    expect(valueProblem("x".repeat(VALUE_MIN - 1))).toMatch(/at least 8/);
    expect(valueProblem("x".repeat(VALUE_MIN))).toBeNull();
  });

  it("keeps spaces: a value is used exactly as typed", () => {
    expect(valueProblem("  spaced value  ")).toBeNull();
  });

  it("has a ceiling", () => {
    expect(valueProblem("x".repeat(VALUE_MAX))).toBeNull();
    expect(valueProblem("x".repeat(VALUE_MAX + 1))).toMatch(/at most/);
  });
});
