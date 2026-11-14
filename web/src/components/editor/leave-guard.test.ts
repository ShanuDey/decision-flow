import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./actions", () => ({ save: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import { guardedLeave, useLeave } from "./leave-store";
import { useEditor } from "./store";

beforeEach(() => {
  useLeave.getState().clear();
  useEditor.setState({ dirty: false });
});

describe("guardedLeave", () => {
  it("runs the action straight away when nothing is unsaved", () => {
    const action = vi.fn();
    guardedLeave(action);
    expect(action).toHaveBeenCalledOnce();
    expect(useLeave.getState().pending).toBeNull();
  });

  it("holds the action until the user decides when there are unsaved changes", () => {
    useEditor.setState({ dirty: true });
    const action = vi.fn();
    guardedLeave(action);
    expect(action).not.toHaveBeenCalled();
    expect(useLeave.getState().pending).toBe(action);
    useLeave.getState().clear();
    expect(useLeave.getState().pending).toBeNull();
  });
});
