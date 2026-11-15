import { describe, expect, it } from "vitest";

import { describeFailure, MAX_RESULT_CHARS, resultOf, truncate } from "./result";

const body = (code: string, message: string, details: object = {}) => JSON.stringify({ code, message, details });

describe("describeFailure", () => {
  it("leads with the code and message", () => {
    expect(describeFailure(404, body("not_found", "Flow not found"), null)).toBe("not_found: Flow not found");
  });

  it("lists validation problems with where they are", () => {
    const text = describeFailure(
      422,
      body("invalid_flow", "End needs a value", {
        errors: [
          { node_id: "end", field: "outputs.0.value", message: "End needs a value" },
          { message: "no start node" },
        ],
      }),
      null,
    );
    expect(text).toContain("- end / outputs.0.value: End needs a value");
    expect(text).toContain("- no start node");
  });

  it("caps a long list of problems", () => {
    const errors = Array.from({ length: 14 }, (_, i) => ({ message: `problem ${i}` }));
    const text = describeFailure(422, body("invalid_flow", "bad", { errors }), null);
    expect(text).toContain("problem 9");
    expect(text).not.toContain("problem 10");
    expect(text).toContain("...and 4 more");
  });

  it("tells the agent how to recover from a stale draft", () => {
    const text = describeFailure(409, body("draft_conflict", "The draft changed", { draft_version: 7 }), null);
    expect(text).toContain("current draft_version is 7");
    expect(text).toContain("get_flow");
  });

  it("points a missing If-Match at get_flow", () => {
    expect(describeFailure(428, body("precondition_required", "If-Match required"), null)).toContain("if_match");
  });

  it("adds the wait when the server gave one", () => {
    expect(describeFailure(502, body("upstream_unavailable", "Starting up"), "30")).toContain("Retry after about 30 seconds.");
    expect(describeFailure(429, body("rate_limited", "Slow down"), "soon")).not.toContain("Retry after");
  });

  it("copes with a body that is not our error shape", () => {
    expect(describeFailure(500, "Internal Server Error", null)).toBe("Request failed (HTTP 500).");
    expect(describeFailure(500, "", null)).toBe("Request failed (HTTP 500).");
    expect(describeFailure(500, '{"detail":"x"}', null)).toContain("HTTP 500");
  });
});

describe("truncate", () => {
  it("leaves short text alone", () => {
    expect(truncate("short")).toBe("short");
  });

  it("cuts long text and says how much was dropped", () => {
    const out = truncate("x".repeat(MAX_RESULT_CHARS + 25));
    expect(out.startsWith("x".repeat(MAX_RESULT_CHARS))).toBe(true);
    expect(out).toContain("25 more characters");
  });
});

describe("resultOf", () => {
  it("returns the body of a success as text", async () => {
    const result = await resultOf(new Response('{"items":[]}', { status: 200 }));
    expect(result.isError).toBeUndefined();
    expect(result.content).toEqual([{ type: "text", text: '{"items":[]}' }]);
  });

  it("says Done for an empty success", async () => {
    expect((await resultOf(new Response(null, { status: 204 }))).content).toEqual([{ type: "text", text: "Done." }]);
  });

  it("turns an error response into an error result", async () => {
    const result = await resultOf(new Response(body("not_found", "Flow not found"), { status: 404 }));
    expect(result.isError).toBe(true);
    expect(result.content).toEqual([{ type: "text", text: "not_found: Flow not found" }]);
  });
});
