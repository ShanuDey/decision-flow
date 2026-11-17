import { toast } from "sonner";

import { errorToast } from "@/lib/api-error";
import { calledByText } from "@/lib/callers";
import { type ApiFailure, call, issuesOf } from "@/lib/call";
import { createRun, getFlow, listCallers, publishFlow, saveDraft, validateFlow } from "@/lib/api/client";
import type { RunResponse } from "@/lib/api/models";
import { parseDraft } from "@/lib/graph/convert";
import { tidy } from "@/lib/graph/tidy";

import { useLayout } from "./layout";
import { publishedInfo } from "./published";
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
    published: publishedInfo(result.data),
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

export type PublishResult = "published" | "invalid" | "unchanged" | "error";

export async function publish(): Promise<PublishResult> {
  if (useEditor.getState().dirty && !(await save())) return "error";
  const result = await call(publishFlow(useEditor.getState().flowId));
  if (result.ok) {
    useEditor.getState().setIssues([]);
    useEditor.getState().markPublished(result.data.version, result.data.source_draft_version);
    const message = `Published version ${result.data.version}`;
    const id = toast.success(message);
    void call(listCallers(useEditor.getState().flowId)).then((callers) => {
      if (callers.ok && callers.data.items.length > 0) {
        toast.success(message, { id, description: calledByText(callers.data.items) });
      }
    });
    return "published";
  }
  const { code } = result.error;
  if (code === "invalid_flow") {
    useEditor.getState().setIssues(issuesOf(result.error));
    return "invalid";
  }
  if (code === "nothing_to_publish") {
    toast.info("Nothing to publish: the draft matches the published version.");
    return "unchanged";
  }
  if (code === "draft_conflict") {
    toast.error("The draft changed elsewhere while publishing.", {
      action: { label: "Load latest", onClick: () => void reloadLatest() },
      duration: 10000,
    });
    return "error";
  }
  errorToast("Could not publish", result.error);
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

export function tidyCanvas(): void {
  const { nodes, edges, moveNodes } = useEditor.getState();
  if (!nodes.length) return;
  const sizes = Object.fromEntries(
    nodes.flatMap((n) =>
      n.measured?.width && n.measured?.height
        ? [[n.id, { width: n.measured.width, height: n.measured.height }]]
        : [],
    ),
  );
  const before = Object.fromEntries(nodes.map((n) => [n.id, n.position]));
  moveNodes(tidy(nodes, edges, sizes));
  toast("Tidied up the layout", {
    action: { label: "Undo", onClick: () => useEditor.getState().moveNodes(before) },
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
