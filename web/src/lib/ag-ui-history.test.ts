import { describe, expect, it } from "vitest";

import type { MessageInfo } from "@/lib/api/models";

import { historyToAgUi, storedMessageId } from "./ag-ui-history";

const ID = "0a6c2f7e-4b1d-4e0a-8c55-3d1e9f2a7b64";

function message(change: Partial<MessageInfo>): MessageInfo {
  return {
    id: ID,
    seq: 1,
    role: "assistant",
    content: "It is six",
    steps: null,
    usage: null,
    model: null,
    traced: false,
    created_at: "2026-11-22T10:00:00",
    ...change,
  } as MessageInfo;
}

describe("historyToAgUi", () => {
  it("keeps a user message and a plain answer as they are", () => {
    const got = historyToAgUi([message({ role: "user", content: "Hi", id: "u1" }), message({})]);
    expect(got).toEqual([
      { id: "u1", role: "user", content: "Hi" },
      { id: ID, role: "assistant", content: "It is six" },
    ]);
  });

  it("puts each flow the agent ran before the answer, as a call and its result", () => {
    const steps = [
      { name: "double", arguments: { amount: 6 }, result: '{"total": 6}', is_error: false },
      { name: "check", arguments: {}, result: "error: nope", is_error: true },
    ];
    const got = historyToAgUi([message({ steps })]);
    expect(got.map((m) => m.role)).toEqual(["assistant", "tool", "tool", "assistant"]);
    const calls = got[0];
    expect(calls.role === "assistant" && calls.toolCalls?.map((c) => c.function.name)).toEqual(["double", "check"]);
    expect(calls.role === "assistant" && calls.toolCalls?.[0].function.arguments).toBe('{"amount":6}');
    expect(got[1]).toMatchObject({ role: "tool", toolCallId: `${ID}:t1`, content: '{"total": 6}' });
    expect(got[3]).toEqual({ id: ID, role: "assistant", content: "It is six" });
  });

  it("is empty for an empty conversation", () => {
    expect(historyToAgUi([])).toEqual([]);
  });
});

describe("storedMessageId", () => {
  it("finds the stored id in a loaded message's id, and not in a live one", () => {
    expect(storedMessageId(ID)).toBe(ID);
    expect(storedMessageId(`${ID}:calls`)).toBe(ID);
    expect(storedMessageId("99513fb4-5136-4f09-9ac4-4ec778d884e2:m2")).toBeNull();
    expect(storedMessageId("run-1:m2")).toBeNull();
  });
});
