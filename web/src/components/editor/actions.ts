import { toast } from "sonner";

import { errorToast } from "@/lib/api-error";
import { type ApiFailure, call, issuesOf } from "@/lib/call";
import { createRun, getFlow, saveDraft, validateFlow } from "@/lib/api/client";
import type { RunResponse } from "@/lib/api/models";
import { parseDraft } from "@/lib/graph/convert";

import { useLayout } from "./layout";
import { useEditor } from "./store";

export type RunOutcome =
  | { kind: "finished"; input: Record<string, unknown>; run: RunResponse }
  | { kind: "rejected"; input: Record<string, unknown>; error: ApiFailure };

export async function reloadLatest(): Promise<void> {
  // An old Undo toast must not restore nodes into the reloaded graph.
  toast.dismiss();
  const { flowId } = useEditor.getState();
  const result = await call(getFlow(flowId, { cache: "no-store" }));
  const graph = result.ok ? parseDraft(result.data.draft) : null;
  if (!result.ok || !graph) {
    toast.error("Could not reload the latest draft");
    return;
  }
  useEditor.getState().load({
    id: result.data.id,
    name: result.data.name,
    draftVersion: result.data.draft_version,
    graph,
  });
  toast.success("Loaded the latest draft");
}

export async function save(): Promise<boolean> {
  const state = useEditor.getState();
  const revision = state.revision;
  const result = await call(
    saveDraft(state.flowId, { ...state.toGraph() }, {
      headers: { "If-Match": String(state.draftVersion) },
    }),
  );
  if (result.ok) {
    useEditor.getState().markSaved(result.data.draft_version, revision);
    return true;
  }
  if (result.error.status === 409) {
    toast.error("This draft was changed elsewhere. Saving would overwrite it.", {
      action: { label: "Load latest", onClick: () => void reloadLatest() },
      duration: 10000,
    });
  } else {
    errorToast("Could not save", result.error);
  }
  return false;
}

export type ValidateResult = "valid" | "invalid" | "error";

// "error" means we could not find out (failed save, network); `quiet` skips the toasts.
export async function validate({ quiet = false }: { quiet?: boolean } = {}): Promise<ValidateResult> {
  if (useEditor.getState().dirty && !(await save())) return "error";
  const result = await call(validateFlow(useEditor.getState().flowId));
  if (result.ok) {
    useEditor.getState().setIssues([]);
    if (!quiet) toast.success("The flow is valid");
    return "valid";
  }
  const issues = issuesOf(result.error);
  if (result.error.code === "invalid_flow" && issues.length) {
    useEditor.getState().setIssues(issues);
    if (!quiet) toast.error(`${issues.length} problem${issues.length === 1 ? "" : "s"} found`);
    return "invalid";
  }
  errorToast("Could not validate", result.error);
  return "error";
}

// Returns null when the run could not be attempted (the save failed).
export async function runTest(input: Record<string, unknown>): Promise<RunOutcome | null> {
  if (useEditor.getState().dirty && !(await save())) return null;
  const result = await call(createRun(useEditor.getState().flowId, { test: true, input }));
  if (result.ok) {
    useEditor.getState().setIssues([]);
    return { kind: "finished", input, run: result.data };
  }
  if (result.error.code === "invalid_flow") {
    useEditor.getState().setIssues(issuesOf(result.error));
  }
  return { kind: "rejected", input, error: result.error };
}

export function deleteFromCanvas(nodeIds: string[], edgeIds: string[]): void {
  const removed = useEditor.getState().deleteItems(nodeIds, edgeIds);
  const { nodes, edges } = removed;
  if (!nodes.length && !edges.length) {
    if (nodeIds.length) toast.info("A flow needs at least one Start and one End node.");
    return;
  }
  const what =
    nodes.length === 1
      ? `\u201c${nodes[0].data.name}\u201d`
      : nodes.length > 1
        ? `${nodes.length} nodes`
        : edges.length === 1
          ? "connection"
          : `${edges.length} connections`;
  toast(`Deleted ${what}`, {
    action: { label: "Undo", onClick: () => useEditor.getState().restore(removed) },
    duration: 8000,
  });
}

// `select` also highlights the name text (used by Rename).
export function configureNode(id: string, { select = false }: { select?: boolean } = {}): void {
  useEditor.getState().selectOnly(id);
  const layout = useLayout.getState();
  layout.expand();
  // SettingsPanel focuses the field once it has rendered this node.
  layout.requestFocus({ select });
}
