import { beforeEach, describe, expect, it } from "vitest";

import type { Graph } from "@/lib/graph/types";

import { useEditor } from "./store";

const graph: Graph = {
  schema_version: 1,
  variables: [{ name: "total", type: "number" }],
  nodes: [
    { id: "start", type: "start", name: "Start", position: { x: 0, y: 0 }, data: { inputs: [] } },
    {
      id: "assign_values",
      type: "assign",
      name: "Assign values",
      position: { x: 300, y: 0 },
      data: { assignments: [] },
    },
    { id: "end", type: "end", name: "End", position: { x: 600, y: 0 }, data: { outputs: [] } },
  ],
  edges: [
    { id: "e1", source: "start", target: "assign_values", sourceHandle: null },
    { id: "e2", source: "assign_values", target: "end", sourceHandle: null },
  ],
};

const state = () => useEditor.getState();

beforeEach(() => {
  state().load({ id: "f1", name: "Demo", draftVersion: 1, graph });
});

describe("dirty tracking", () => {
  it("starts clean and ignores selection and measuring", () => {
    state().onNodesChange([{ id: "start", type: "select", selected: true }]);
    state().onNodesChange([
      { id: "start", type: "dimensions", dimensions: { width: 10, height: 10 } },
    ]);
    expect(state().dirty).toBe(false);
  });

  it("is dirty after a drag ends, not while dragging", () => {
    const position = { x: 5, y: 5 };
    state().onNodesChange([{ id: "start", type: "position", position, dragging: true }]);
    expect(state().dirty).toBe(false);
    state().onNodesChange([{ id: "start", type: "position", position, dragging: false }]);
    expect(state().dirty).toBe(true);
  });

  it("stays dirty when edits land while a save is in flight", () => {
    state().renameNode("start", "Begin");
    const saving = state().revision; // what save() captures before the request
    state().renameNode("start", "Begin again"); // user keeps typing
    state().markSaved(2, saving);
    expect(state().dirty).toBe(true);
    expect(state().draftVersion).toBe(2);
  });

  it("becomes clean when nothing changed during the save", () => {
    state().renameNode("start", "Begin");
    state().markSaved(2, state().revision);
    expect(state().dirty).toBe(false);
    expect(state().savedAt).not.toBeNull();
  });
});

describe("node rules", () => {
  it("refuses to delete the only Start or End node", () => {
    state().onNodesChange([
      { id: "start", type: "remove" },
      { id: "end", type: "remove" },
    ]);
    expect(state().nodes.map((n) => n.id)).toEqual(["start", "assign_values", "end"]);
  });

  it("deletes an Assign node together with its edges", () => {
    state().onNodesChange([{ id: "assign_values", type: "remove" }]);
    expect(state().nodes.map((n) => n.id)).toEqual(["start", "end"]);
    expect(state().edges).toEqual([]);
    expect(state().dirty).toBe(true);
  });

  it("allows deleting an End node when another remains", () => {
    state().addNode("end");
    const second = state().nodes.find((n) => n.data.name === "End 2")!;
    state().onNodesChange([{ id: second.id, type: "remove" }]);
    expect(state().nodes.some((n) => n.id === second.id)).toBe(false);
  });

  it("adds Assign nodes with unique names but never a second Start", () => {
    state().addNode("assign");
    state().addNode("assign");
    state().addNode("start");
    const names = state().nodes.map((n) => n.data.name);
    expect(names).toContain("Assign values 2");
    expect(names).toContain("Assign values 3");
    expect(names.filter((n) => n.startsWith("Start"))).toEqual(["Start"]);
  });

  it("validates connections", () => {
    const ok = (source: string, target: string) =>
      state().isValidConnection({ source, target, sourceHandle: null, targetHandle: null });
    expect(ok("assign_values", "start")).toBe(false); // nothing flows into Start
    expect(ok("end", "assign_values")).toBe(false); // nothing flows out of End
    expect(ok("assign_values", "assign_values")).toBe(false); // no self loops
    expect(ok("start", "assign_values")).toBe(false); // duplicate edge
    expect(ok("start", "end")).toBe(true);
  });
});

describe("round trip", () => {
  it("exports the graph it was loaded with", () => {
    expect(state().toGraph()).toEqual(graph);
  });
});
