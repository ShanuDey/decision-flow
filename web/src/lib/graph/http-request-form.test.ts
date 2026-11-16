import { describe, expect, it } from "vitest";

import {
  apiKeyHeader,
  bearerHeader,
  bodyOnTypeChange,
  headerNameCheck,
  jsonText,
  parseJson,
  parseTimeout,
  recordOf,
  rowProblem,
  rowsOf,
  withHeader,
} from "./http-request";

describe("rows", () => {
  it("round-trips a record in order", () => {
    const rows = rowsOf({ b: "2", a: "1" });
    expect(rows).toEqual([
      { name: "b", value: "2" },
      { name: "a", value: "1" },
    ]);
    expect(Object.keys(recordOf(rows))).toEqual(["b", "a"]);
    expect(rowsOf(null)).toEqual([]);
  });

  it("flags a blank name and a repeated one, on the later row only", () => {
    const rows = [
      { name: "a", value: "1" },
      { name: "", value: "x" },
      { name: " ", value: "x" },
      { name: "a", value: "2" },
    ];
    expect(rows.map((_, i) => rowProblem(rows, i))).toEqual([
      null,
      "Enter a name",
      "Enter a name",
      "This name is already used",
    ]);
    expect(recordOf(rows)).toEqual({ a: "1" });
  });

  it("treats header names as case-insensitive and query names as exact", () => {
    const rows = [
      { name: "Accept", value: "1" },
      { name: "accept", value: "2" },
    ];
    expect(rowProblem(rows, 1, undefined, true)).toBe("This name is already used");
    expect(rowProblem(rows, 1)).toBeNull();
    expect(recordOf(rows, undefined, true)).toEqual({ Accept: "1" });
  });

  it("checks header names", () => {
    expect(headerNameCheck("X-Api-Key")).toBeNull();
    expect(headerNameCheck("Bad Header")).toBe("Not a valid header name");
    expect(headerNameCheck("a:b")).toBe("Not a valid header name");
    const rows = [{ name: "Bad Header", value: "x" }];
    expect(rowProblem(rows, 0, headerNameCheck)).toBe("Not a valid header name");
    expect(recordOf(rows, headerNameCheck)).toEqual({});
  });

  it("refuses the headers the server sets itself, whatever their case", () => {
    for (const name of ["Host", "content-length", "Transfer-Encoding", "CONNECTION", "Upgrade", "TE"]) {
      expect(headerNameCheck(name)).toBe("This header is set by the server");
    }
    expect(headerNameCheck("Content-Type")).toBeNull();
    expect(headerNameCheck("Authorization")).toBeNull();
  });
});

describe("authentication presets", () => {
  it("builds a bearer header and an API key header from a secret name", () => {
    expect(bearerHeader("STRIPE_KEY")).toEqual({
      name: "Authorization",
      value: "Bearer {{ secrets.STRIPE_KEY }}",
    });
    expect(apiKeyHeader("SCORE_KEY")).toEqual({ name: "X-Api-Key", value: "{{ secrets.SCORE_KEY }}" });
    expect(apiKeyHeader("SCORE_KEY", "X-Token").name).toBe("X-Token");
  });

  it("adds a header, or replaces the one with the same name whatever its case", () => {
    const rows = [{ name: "authorization", value: "old" }, { name: "Accept", value: "json" }];
    expect(withHeader(rows, bearerHeader("K"))).toEqual([
      { name: "Authorization", value: "Bearer {{ secrets.K }}" },
      { name: "Accept", value: "json" },
    ]);
    expect(withHeader([], bearerHeader("K"))).toHaveLength(1);
    expect(withHeader(rows, apiKeyHeader("K"))).toHaveLength(3);
  });
});

describe("body", () => {
  it("starts each body type empty, and keeps the body when the type does not change", () => {
    expect(bodyOnTypeChange("none", "json", null)).toEqual({});
    expect(bodyOnTypeChange("json", "form", { a: 1 })).toEqual({});
    expect(bodyOnTypeChange("form", "text", { a: "1" })).toBe("");
    expect(bodyOnTypeChange("text", "none", "x")).toBeNull();
    expect(bodyOnTypeChange("json", "json", { a: 1 })).toEqual({ a: 1 });
  });

  it("shows JSON readably and parses what is typed", () => {
    expect(jsonText({ a: ["{{ input.x }}"] })).toBe('{\n  "a": [\n    "{{ input.x }}"\n  ]\n}');
    expect(jsonText(null)).toBe("{}");
    expect(parseJson('{"a": 1}')).toEqual({ ok: true, value: { a: 1 } });
    expect(parseJson("[1, 2]")).toEqual({ ok: true, value: [1, 2] });
    const bad = parseJson('{"a": ');
    expect(bad.ok).toBe(false);
    expect(parseJson("").ok).toBe(false);
  });
});

describe("timeout", () => {
  it("accepts blank or a whole number of seconds from 1", () => {
    expect(parseTimeout("")).toEqual({ ok: true, value: null });
    expect(parseTimeout(" ")).toEqual({ ok: true, value: null });
    expect(parseTimeout("10")).toEqual({ ok: true, value: 10 });
    for (const bad of ["0", "-1", "1.5", "abc"]) expect(parseTimeout(bad).ok).toBe(false);
  });
});
