import { describe, expect, it } from "vitest";

import { triggerBody, triggerTarget } from "./trigger";

describe("triggerTarget", () => {
  it("maps a trigger path to the run route", () => {
    expect(triggerTarget("/flows/abc-123/trigger")).toBe("/flows/abc-123/runs");
  });

  it.each(["/flows/abc/runs", "/flows/abc/trigger/x", "/flows//trigger", "/flows/trigger", "/trigger"])(
    "ignores %s",
    (path) => {
      expect(triggerTarget(path)).toBeNull();
    },
  );
});

describe("triggerBody", () => {
  const parse = (text: string) => {
    const result = triggerBody(text);
    if (!result.ok) throw new Error(result.message);
    return JSON.parse(result.body);
  };

  it("wraps the input and always runs the published version", () => {
    expect(parse('{"input": {"amount": 5}}')).toEqual({ input: { amount: 5 }, test: false });
  });

  it("treats an empty body or missing input as no input", () => {
    expect(parse("")).toEqual({ input: {}, test: false });
    expect(parse("  ")).toEqual({ input: {}, test: false });
    expect(parse("{}")).toEqual({ input: {}, test: false });
  });

  it("refuses a test flag instead of forwarding it", () => {
    const result = triggerBody('{"input": {}, "test": true}');
    expect(result).toMatchObject({ ok: false });
    expect(result.ok ? "" : result.message).toContain('"test"');
  });

  it("points out flat input sent without the input wrapper", () => {
    const result = triggerBody('{"amount": 5}');
    expect(result.ok ? "" : result.message).toContain('"amount"');
  });

  it.each([
    ["invalid JSON", "{nope"],
    ["an array", "[1]"],
    ["a string", '"x"'],
    ["null", "null"],
    ["input as an array", '{"input": [1]}'],
    ["input as null", '{"input": null}'],
    ["input as a string", '{"input": "5"}'],
  ])("rejects %s", (_label, text) => {
    expect(triggerBody(text).ok).toBe(false);
  });
});
