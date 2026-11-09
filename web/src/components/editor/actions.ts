import { toast } from "sonner";

import { type ApiFailure, call, issuesOf } from "@/lib/call";
import { createRun, getFlow, saveDraft, validateFlow } from "@/lib/api/client";
import type { RunResponse } from "@/lib/api/models";
import { parseDraft } from "@/lib/graph/convert";

import { useEditor } from "./store";

export type RunOutcome =
  | { kind: "finished"; input: Record<string, unknown>; run: RunResponse }
  | { kind: "rejected"; input: Record<string, unknown>; error: ApiFailure };

export async function reloadLatest(): Promise<void> {
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
    toast.error(`Could not save: ${result.error.message}`);
  }
  return false;
}

export async function validate(): Promise<void> {
  if (useEditor.getState().dirty && !(await save())) return;
  const result = await call(validateFlow(useEditor.getState().flowId));
  if (result.ok) {
    useEditor.getState().setIssues([]);
    toast.success("The flow is valid");
    return;
  }
  const issues = issuesOf(result.error);
  if (result.error.code === "invalid_flow" && issues.length) {
    useEditor.getState().setIssues(issues);
    toast.error(`${issues.length} problem${issues.length === 1 ? "" : "s"} found`);
  } else {
    toast.error(`Could not validate: ${result.error.message}`);
  }
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
