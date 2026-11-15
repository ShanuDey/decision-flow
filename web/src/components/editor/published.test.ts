import { describe, expect, it } from "vitest";

import { keepNote, publishedInfo } from "./published";

describe("keepNote", () => {
  it("says nothing when every version is kept", () => {
    expect(keepNote(0)).toBeNull();
  });

  it("explains the window", () => {
    expect(keepNote(10)).toBe("Only the newest 10 versions are kept. Older ones are deleted when you publish.");
    expect(keepNote(1)).toBe("Only the newest 1 version is kept. Older ones are deleted when you publish.");
  });
});

describe("publishedInfo", () => {
  it("is null for a flow that was never published", () => {
    expect(publishedInfo({ published_version: null, published_draft_version: null })).toBeNull();
  });

  it("carries the version and the draft it came from", () => {
    expect(publishedInfo({ published_version: 3, published_draft_version: 5 })).toEqual({
      version: 3,
      draftVersion: 5,
    });
  });
});
