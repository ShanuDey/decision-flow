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

  it("gives a Condition one edge per branch, and allows both to reach the same node", () => {
    state().addNode("condition");
    const edge = (sourceHandle: string | null, target: string) =>
      state().isValidConnection({ source: "condition", target, sourceHandle, targetHandle: null });
    expect(edge(null, "end")).toBe(false); // must leave from a branch
    expect(edge("true", "end")).toBe(true);
    state().onConnect({ source: "condition", target: "end", sourceHandle: "true", targetHandle: null });
    expect(edge("true", "assign_values")).toBe(false); // branch already used
    expect(edge("false", "end")).toBe(true);
    expect(state().toGraph().edges.at(-1)?.sourceHandle).toBe("true");
  });

  it("starts a Condition with an empty expression", () => {
    state().addNode("condition");
    const added = state().toGraph().nodes.find((n) => n.type === "condition");
    expect(added?.data).toEqual({ expression: "" });
  });
});

describe("round trip", () => {
  it("exports the graph it was loaded with", () => {
    expect(state().toGraph()).toEqual(graph);
  });
});

describe("addNode with a position", () => {
  it("places the node where asked", () => {
    state().addNode("assign", { x: 123, y: 45 });
    const added = state().nodes.find((n) => n.id === "assign_values_2")!;
    expect(added.position).toEqual({ x: 123, y: 45 });
    expect(added.selected).toBe(true);
  });
});

describe("duplicateNode", () => {
  it("copies the settings into an independent node with a unique name and id, without edges", () => {
    state().setNodeConfig("assign_values", {
      assignments: [{ variable: "total", value: "{{ input.amount }}" }],
    });
    const id = state().duplicateNode("assign_values");
    expect(id).toBe("assign_values_2");

    const copy = state().nodes.find((n) => n.id === id)!;
    expect(copy.data.name).toBe("Assign values 2");
    expect(copy.position).toEqual({ x: 340, y: 40 });
    expect(copy.data.config).toEqual({
      assignments: [{ variable: "total", value: "{{ input.amount }}" }],
    });
    state().setNodeConfig(id!, { assignments: [] });
    const original = state().nodes.find((n) => n.id === "assign_values")!;
    expect(original.data.config).toEqual({
      assignments: [{ variable: "total", value: "{{ input.amount }}" }],
    });
    expect(state().edges.filter((e) => e.source === id || e.target === id)).toEqual([]);
    expect(state().nodes.filter((n) => n.selected).map((n) => n.id)).toEqual([id]);
  });

  it("refuses to duplicate Start, and unknown nodes", () => {
    expect(state().duplicateNode("start")).toBeNull();
    expect(state().duplicateNode("nope")).toBeNull();
    expect(state().nodes).toHaveLength(3);
  });
});

describe("deleteItems and restore", () => {
  it("returns the node together with its edges, and restore puts them back", () => {
    const removed = state().deleteItems(["assign_values"], []);
    expect(removed.nodes.map((n) => n.id)).toEqual(["assign_values"]);
    expect(removed.edges.map((e) => e.id).sort()).toEqual(["e1", "e2"]);
    expect(state().nodes.map((n) => n.id)).toEqual(["start", "end"]);
    expect(state().edges).toEqual([]);

    state().restore(removed);
    expect(state().nodes.map((n) => n.id).sort()).toEqual(["assign_values", "end", "start"]);
    expect(state().edges.map((e) => e.id).sort()).toEqual(["e1", "e2"]);
    expect(state().toGraph().edges).toEqual(graph.edges);
  });

  it("deletes a single edge and can restore it", () => {
    const removed = state().deleteItems([], ["e1"]);
    expect(removed.nodes).toEqual([]);
    expect(removed.edges.map((e) => e.id)).toEqual(["e1"]);
    expect(state().edges.map((e) => e.id)).toEqual(["e2"]);
    state().restore(removed);
    expect(state().edges.map((e) => e.id).sort()).toEqual(["e1", "e2"]);
  });

  it("refuses to delete the only Start or End and reports nothing removed", () => {
    const removed = state().deleteItems(["start", "end"], []);
    expect(removed).toEqual({ nodes: [], edges: [] });
    expect(state().nodes).toHaveLength(3);
    expect(state().dirty).toBe(false);
  });

  it("marks the draft dirty on delete and on restore", () => {
    const removed = state().deleteItems([], ["e2"]);
    expect(state().dirty).toBe(true);
    state().markSaved(2, state().revision);
    expect(state().dirty).toBe(false);
    state().restore(removed);
    expect(state().dirty).toBe(true);
  });

  it("restore skips ids that were taken meanwhile and edges with missing ends", () => {
    const removed = state().deleteItems(["assign_values"], []);
    state().addNode("assign"); // takes the freed id "assign_values"
    const before = state().nodes.length;
    state().restore(removed);
    expect(state().nodes).toHaveLength(before);
    expect(state().edges.map((e) => e.id)).toEqual([]); // not rewired to the unrelated new node
  });

  it("restoring twice does not duplicate anything", () => {
    const removed = state().deleteItems(["assign_values"], []);
    state().restore(removed);
    const revision = state().revision;
    state().restore(removed);
    expect(state().nodes).toHaveLength(3);
    expect(state().revision).toBe(revision); // a no-op restore is not a change
  });
});

describe("selectOnly", () => {
  it("selects exactly one node without touching the draft", () => {
    state().selectOnly("assign_values");
    expect(state().nodes.filter((n) => n.selected).map((n) => n.id)).toEqual(["assign_values"]);
    state().selectOnly("end");
    expect(state().nodes.filter((n) => n.selected).map((n) => n.id)).toEqual(["end"]);
    expect(state().dirty).toBe(false);
    expect(state().revision).toBe(0);
  });

  it("deselects everything for an unknown id", () => {
    state().selectOnly("start");
    state().selectOnly("nope");
    expect(state().nodes.some((n) => n.selected)).toBe(false);
  });
});
