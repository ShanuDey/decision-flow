import { describe, expect, it } from "vitest";

import { calledByText, callersOf } from "./callers";

describe("callersOf", () => {
  it("reads the callers of a flow_in_use answer", () => {
    expect(callersOf({ callers: [{ id: "a", name: "Loan check" }] })).toEqual([{ id: "a", name: "Loan check" }]);
  });

  it("ignores anything malformed", () => {
    expect(callersOf({})).toEqual([]);
    expect(callersOf({ callers: "nope" })).toEqual([]);
    expect(callersOf({ callers: [null, { id: 1, name: "x" }, { id: "b", name: "ok" }] })).toEqual([
      { id: "b", name: "ok" },
    ]);
  });
});

describe("calledByText", () => {
  it("names the callers and counts the rest", () => {
    const one = [{ id: "a", name: "A" }];
    expect(calledByText(one)).toBe("Called by 1 flow: A");
    const five = ["A", "B", "C", "D", "E"].map((name) => ({ id: name, name }));
    expect(calledByText(five)).toBe("Called by 5 flows: A, B, C and 2 more");
  });
});
