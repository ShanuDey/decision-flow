import { describe, expect, it } from "vitest";

import type { ThreadSummary } from "@/lib/api/models";

import { type AgentForm, argsSummary, formProblem, groupByDay, sameForm, uniqueName, updateBody, whoKind, whoLabel, groupByAgent } from "./agents";

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

describe("argsSummary", () => {
  it("lists each argument on one line", () => {
    expect(argsSummary({ income: 45000, who: "Ada", tags: ["a"] })).toBe('income 45000 · who Ada · tags ["a"]');
    expect(argsSummary({})).toBe("");
    expect(argsSummary(undefined)).toBe("");
  });
});

describe("groupByDay", () => {
  const thread = (id: string, updated_at: string): ThreadSummary =>
    ({ id, agent_id: "a", title: id, created_at: updated_at, updated_at }) as ThreadSummary;
  const now = new Date(2026, 10, 22, 12, 0, 0);

  it("puts each conversation under the day it was last active, and drops empty groups", () => {
    const local = (day: number, hour: number) => new Date(2026, 10, day, hour).toISOString();
    const groups = groupByDay(
      [thread("t1", local(22, 9)), thread("t2", local(21, 23)), thread("t3", local(10, 8)), thread("t4", local(22, 1))],
      now,
    );
    expect(groups.map((g) => [g.label, g.items.map((t) => t.id)])).toEqual([
      ["Today", ["t1", "t4"]],
      ["Yesterday", ["t2"]],
      ["Earlier", ["t3"]],
    ]);
    expect(groupByDay([], now)).toEqual([]);
  });
});

describe("whoLabel", () => {
  it("says nothing for a team member and names an outside app's user", () => {
    expect(whoLabel({ source: "web", external_user_id: null, anonymous: false })).toBeNull();
    expect(whoLabel({ source: "api", external_user_id: "maria@acme.com", anonymous: false })).toBe("External · maria@acme.com");
  });

  it("shortens a generated anonymous id", () => {
    expect(whoLabel({ source: "api", external_user_id: "anon-a1b2c3d4e5f6", anonymous: true })).toBe("Anonymous · a1b2c3");
  });
});

describe("whoKind", () => {
  it("tells the team, outside users and anonymous ones apart", () => {
    expect(whoKind({ source: "web", anonymous: false })).toBe("team");
    expect(whoKind({ source: "api", anonymous: false })).toBe("external");
    expect(whoKind({ source: "api", anonymous: true })).toBe("anonymous");
  });
});

describe("groupByAgent", () => {
  const thread = (id: string, agent_id: string) => ({ id, agent_id }) as ThreadSummary;

  it("groups under each agent in the order of the newest conversation and names unknown agents", () => {
    const groups = groupByAgent([thread("t1", "b"), thread("t2", "a"), thread("t3", "b"), thread("t4", "gone")], {
      a: "Alpha",
      b: "Beta",
    });
    expect(groups.map((g) => [g.name, g.items.map((t) => t.id)])).toEqual([
      ["Beta", ["t1", "t3"]],
      ["Alpha", ["t2"]],
      ["Unknown agent", ["t4"]],
    ]);
    expect(groupByAgent([], {})).toEqual([]);
  });
});
