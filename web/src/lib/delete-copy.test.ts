import { describe, expect, it } from "vitest";

import { deleteCopy } from "./delete-copy";

describe("deleteCopy", () => {
  it("warns that a hard delete is permanent", () => {
    expect(deleteCopy("hard", "Loan check")).toBe(
      "This deletes \u201cLoan check\u201d, its published versions and all of its runs. It cannot be undone.",
    );
  });

  it("says a soft delete keeps the history", () => {
    expect(deleteCopy("soft", "Loan check")).toBe(
      "\u201cLoan check\u201d will be removed from your flows. Its versions and runs are kept for audit.",
    );
  });
});
