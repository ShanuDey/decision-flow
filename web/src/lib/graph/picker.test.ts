import { describe, expect, it } from "vitest";

import { flatTypes, ioSummary, pickerGroups } from "./picker";

describe("pickerGroups", () => {
  it("groups every built-in node in a stable order", () => {
    const groups = pickerGroups("", "all");
    expect(groups.map((g) => g.group)).toEqual(["Flow", "Logic", "Data"]);
    expect(flatTypes(groups).sort()).toEqual(["assign", "condition", "end", "start"]);
  });

  it("filters by search text across label and description", () => {
    expect(flatTypes(pickerGroups("branch", "all"))).toEqual(["condition"]);
    expect(flatTypes(pickerGroups("  ASSIGN ", "all"))).toEqual(["assign"]);
    expect(pickerGroups("zzz", "all")).toEqual([]);
  });

  it("filters by source and has no community nodes yet", () => {
    expect(flatTypes(pickerGroups("", "builtin")).length).toBe(4);
    expect(pickerGroups("", "community")).toEqual([]);
  });
});

describe("ioSummary", () => {
  it("describes inputs and outputs from the node spec", () => {
    expect(ioSummary("condition")).toEqual({ inputs: "1", outputs: "true, false" });
    expect(ioSummary("start")).toEqual({ inputs: "none", outputs: "1" });
    expect(ioSummary("end")).toEqual({ inputs: "1", outputs: "none" });
  });
});
