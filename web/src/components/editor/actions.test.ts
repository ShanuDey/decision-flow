import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Graph } from "@/lib/graph/types";

const { toast } = vi.hoisted(() => ({
  toast: Object.assign(vi.fn(), {
    info: vi.fn(),
    error: vi.fn(),
    success: vi.fn(),
    dismiss: vi.fn(),
  }),
}));

vi.mock("sonner", () => ({ toast }));
vi.mock("@/lib/api/client", () => ({
  getFlow: vi.fn(),
  saveDraft: vi.fn(),
  validateFlow: vi.fn(),
  createRun: vi.fn(),
}));

import { getFlow, saveDraft, validateFlow } from "@/lib/api/client";

import { configureNode, deleteFromCanvas, reloadLatest, validate } from "./actions";
import { useLayout } from "./layout";
import { useEditor } from "./store";

const graph: Graph = {
  schema_version: 1,
  variables: [],
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

const ids = () => useEditor.getState().nodes.map((n) => n.id);

beforeEach(() => {
  vi.clearAllMocks();
  useEditor.getState().load({ id: "f1", name: "Demo", draftVersion: 1, graph });
  useLayout.setState({ collapsed: false, focusRequest: null });
});

describe("deleteFromCanvas", () => {
  it("offers an Undo that puts the node and its connections back", () => {
    deleteFromCanvas(["assign_values"], []);
    expect(ids()).toEqual(["start", "end"]);
    const [message, options] = toast.mock.calls[0];
    expect(message).toBe("Deleted \u201cAssign values\u201d");

    options.action.onClick();
    expect(ids().sort()).toEqual(["assign_values", "end", "start"]);
    expect(useEditor.getState().edges.map((e) => e.id).sort()).toEqual(["e1", "e2"]);
  });

  it("names a deleted connection as such", () => {
    deleteFromCanvas([], ["e1"]);
    expect(toast.mock.calls[0][0]).toBe("Deleted connection");
  });

  it("explains instead of deleting the only Start, and offers no Undo", () => {
    deleteFromCanvas(["start"], []);
    expect(ids()).toContain("start");
    expect(toast).not.toHaveBeenCalled();
    expect(toast.info).toHaveBeenCalledOnce();
  });
});

describe("configureNode", () => {
  it("selects the node, expands a collapsed panel and requests focus", () => {
    useLayout.setState({ collapsed: true });
    configureNode("assign_values");
    expect(useEditor.getState().nodes.filter((n) => n.selected).map((n) => n.id)).toEqual([
      "assign_values",
    ]);
    expect(useLayout.getState().collapsed).toBe(false);
    expect(useLayout.getState().focusRequest).toEqual({ select: false });
  });

  it("asks to select the name text for Rename, and re-requests on every call", () => {
    configureNode("end", { select: true });
    const first = useLayout.getState().focusRequest;
    expect(first).toEqual({ select: true });
    configureNode("end", { select: true });
    expect(useLayout.getState().focusRequest).not.toBe(first);
  });

  it("does not make the draft dirty", () => {
    configureNode("end");
    expect(useEditor.getState().dirty).toBe(false);
  });
});

describe("reloadLatest", () => {
  it("dismisses toasts first so an old Undo cannot touch the reloaded graph", async () => {
    vi.mocked(getFlow).mockResolvedValue({
      status: 404,
      data: { code: "not_found", message: "gone", details: {} },
      headers: new Headers(),
    } as never);
    await reloadLatest();
    expect(toast.dismiss).toHaveBeenCalled();
    expect(toast.dismiss.mock.invocationCallOrder[0]).toBeLessThan(
      vi.mocked(getFlow).mock.invocationCallOrder[0],
    );
    expect(toast.error).toHaveBeenCalled();
  });
});

describe("validate", () => {
  const reply = (status: number, data: unknown) => Promise.resolve({ status, data });
  const mocked = <T,>(fn: T) => fn as unknown as ReturnType<typeof vi.fn>;

  it('says "valid" and clears old issues when the API accepts the flow', async () => {
    useEditor.getState().setIssues([{ code: "x", message: "old", node_id: null, field: null }]);
    mocked(validateFlow).mockReturnValue(reply(200, { valid: true }));
    expect(await validate({ quiet: true })).toBe("valid");
    expect(useEditor.getState().issues).toEqual([]);
  });

  it('says "invalid" and keeps the issues when the API lists problems', async () => {
    mocked(validateFlow).mockReturnValue(
      reply(422, {
        code: "invalid_flow",
        message: "bad",
        details: { errors: [{ code: "c", message: "m", node_id: "end", field: null }] },
      }),
    );
    expect(await validate({ quiet: true })).toBe("invalid");
    expect(useEditor.getState().issues).toHaveLength(1);
  });

  it('says "error", not "valid", when it could not find out', async () => {
    mocked(validateFlow).mockReturnValue(reply(500, { code: "boom", message: "Server error", details: {} }));
    expect(await validate({ quiet: true })).toBe("error");
    expect(useEditor.getState().issues).toEqual([]);
    expect(toast.error).toHaveBeenCalled();
  });

  it('says "error" without validating when the save that must come first fails', async () => {
    useEditor.setState({ dirty: true });
    mocked(saveDraft).mockReturnValue(reply(500, { code: "boom", message: "Server error", details: {} }));
    mocked(validateFlow).mockClear();
    expect(await validate({ quiet: true })).toBe("error");
    expect(validateFlow).not.toHaveBeenCalled();
  });
});
