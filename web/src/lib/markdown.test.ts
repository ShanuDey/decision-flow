import { describe, expect, it } from "vitest";

import { safeHref } from "./markdown";

describe("safeHref", () => {
  it.each([
    ["https://docs.github.com/rest", "https://docs.github.com/rest"],
    ["http://example.com", "http://example.com"],
    ["mailto:team@example.com", "mailto:team@example.com"],
    ["  https://example.com/a  ", "https://example.com/a"],
  ])("keeps %s", (input, expected) => {
    expect(safeHref(input)).toBe(expected);
  });

  it.each([
    "javascript:alert(1)",
    "JaVaScRiPt:alert(1)",
    " javascript:alert(1)",
    "data:text/html,<b>x</b>",
    "vbscript:x",
    "file:///etc/passwd",
    "#set-up",
    "//example.com",
    "/relative/path",
    "example.com",
    "",
  ])("drops %j", (input) => {
    expect(safeHref(input)).toBeUndefined();
  });
});
