import { describe, expect, it } from "vitest";

import { nextVariableName } from "./variables";

describe("nextVariableName", () => {
  it("starts at var_1", () => {
    expect(nextVariableName([])).toBe("var_1");
  });

  it("skips names that are taken", () => {
    const taken = [{ name: "var_1", type: "string" as const }, { name: "var_3", type: "number" as const }];
    expect(nextVariableName(taken)).toBe("var_2");
  });
});
