import { describe, expect, it } from "vitest";

import { dictationProblem } from "./dictation";

describe("dictationProblem", () => {
  it("stays quiet when the person simply said nothing or stopped", () => {
    expect(dictationProblem("no-speech")).toBeNull();
    expect(dictationProblem("aborted")).toBeNull();
  });

  it("explains each failure the person can act on", () => {
    for (const code of ["network", "service-not-allowed", "language-not-supported"]) {
      expect(dictationProblem(code)).toMatch(/Chrome or Edge/);
    }
    expect(dictationProblem("not-allowed")).toMatch(/Microphone access/);
    expect(dictationProblem("audio-capture")).toMatch(/No microphone/);
  });

  it("has a fallback for anything else", () => {
    expect(dictationProblem("something-new")).toMatch(/stopped unexpectedly/);
    expect(dictationProblem(undefined)).toMatch(/stopped unexpectedly/);
  });
});
