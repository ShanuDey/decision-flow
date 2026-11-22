import { describe, expect, it } from "vitest";

import { addToken, type AgentForm, formProblem, parseEvents, sameForm, stepSummary, uniqueName, updateBody } from "./agents";

const FLOW = "0a6c2f7e-4b1d-4e0a-8c55-3d1e9f2a7b64";

function form(change: Partial<AgentForm> = {}): AgentForm {
  return {
    name: "Helper",
    description: "",
    connection_id: "",
    model: "",
    instructions: "",
    tools: [],
    max_iterations: 8,
    max_total_tokens: null,
    max_seconds: null,
    temperature: null,
    max_tokens: null,
    timeout_seconds: null,
    ...change,
  };
}

describe("updateBody", () => {
  it("sends null for a cleared connection and cleared limits", () => {
    const body = updateBody(form({ name: " Helper ", model: " m " }));
    expect(body).toMatchObject({ name: "Helper", model: "m", connection_id: null, max_total_tokens: null });
    expect(updateBody(form({ connection_id: "c1" })).connection_id).toBe("c1");
  });
});

describe("uniqueName", () => {
  it("adds a number until the name is free, ignoring case", () => {
    expect(uniqueName("Agent", [])).toBe("Agent");
    expect(uniqueName("Agent", ["agent", "Agent 2"])).toBe("Agent 3");
  });
});

describe("sameForm", () => {
  it("notices a change anywhere, tools included", () => {
    expect(sameForm(form(), form())).toBe(true);
    expect(sameForm(form(), form({ instructions: "x" }))).toBe(false);
    const tool = { flow_id: FLOW, name: "a", description: "d" };
    expect(sameForm(form({ tools: [tool] }), form({ tools: [{ ...tool, name: "b" }] }))).toBe(false);
  });
});

describe("formProblem", () => {
  const tool = { flow_id: FLOW, name: "lookup", description: "Finds it" };
  it("accepts a good form", () => {
    expect(formProblem(form({ tools: [tool] }))).toBeNull();
  });
  it("names the first problem", () => {
    expect(formProblem(form({ name: " " }))).toMatch(/name/);
    expect(formProblem(form({ tools: [{ ...tool, flow_id: "" }] }))).toBe("Tool 1: pick a flow");
    expect(formProblem(form({ tools: [{ ...tool, name: "bad name" }] }))).toMatch(/Tool 1/);
    expect(formProblem(form({ tools: [tool, tool] }))).toMatch(/Tool 2: another tool/);
    expect(formProblem(form({ tools: [{ ...tool, description: " " }] }))).toMatch(/what it does/);
  });
});

describe("parseEvents", () => {
  const tool = 'event: tool\ndata: {"name":"a","arguments":{},"result":"1","is_error":false}\n\n';
  it("returns the complete events and keeps the unfinished text", () => {
    const { events, rest } = parseEvents(`${tool}event: message\ndata: {"rep`);
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ type: "tool", step: { name: "a" } });
    expect(rest).toBe('event: message\ndata: {"rep');
  });
  it("reads message and error events, even with CRLF line ends", () => {
    const text =
      'event: message\r\ndata: {"reply":{"content":"hi"}}\r\n\r\nevent: error\r\ndata: {"code":"x","message":"m"}\r\n\r\n';
    const { events, rest } = parseEvents(text);
    expect(events.map((e) => e.type)).toEqual(["message", "error"]);
    expect(rest).toBe("");
  });
  it("skips blocks it cannot read", () => {
    expect(parseEvents("event: tool\ndata: {nope\n\nevent: other\ndata: {}\n\n").events).toEqual([]);
  });
});

describe("token events", () => {
  it("are read with their model call number and text", () => {
    const { events } = parseEvents('event: token\ndata: {"index": 2, "text": "It "}\n\n');
    expect(events).toEqual([{ type: "token", index: 2, text: "It " }]);
  });
});

describe("addToken", () => {
  it("grows the text of one model call", () => {
    const first = addToken(null, 1, "Hel");
    expect(addToken(first, 1, "lo")).toEqual({ index: 1, text: "Hello" });
  });
  it("starts over when the next model call begins", () => {
    expect(addToken({ index: 1, text: "Let me check" }, 2, "It")).toEqual({ index: 2, text: "It" });
  });
});

describe("stepSummary", () => {
  it("shows the tool and its arguments", () => {
    const base = { result: "", is_error: false };
    expect(stepSummary({ ...base, name: "check", arguments: { income: 5, who: "Ada" } })).toBe(
      "check(income: 5, who: Ada)",
    );
    expect(stepSummary({ ...base, name: "ping", arguments: {} })).toBe("ping");
  });
});
