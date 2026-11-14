"use client";

import { CircleAlert, CircleCheck } from "lucide-react";

import type { FieldIssue } from "@/lib/call";

import { configureNode } from "./actions";
import { useEditor } from "./store";

export function ValidateIssues({ onPick }: { onPick: () => void }) {
  const issues = useEditor((s) => s.issues);
  const nodes = useEditor((s) => s.nodes);
  const nameOf = (issue: FieldIssue) =>
    issue.node_id ? (nodes.find((n) => n.id === issue.node_id)?.data.name ?? issue.node_id) : "Flow";

  if (issues.length === 0) {
    return (
      <p className="flex items-center gap-2 p-3 text-sm" role="status">
        <CircleCheck className="size-4 text-green-700 dark:text-green-400" aria-hidden />
        The flow is valid.
      </p>
    );
  }

  return (
    <div className="p-2">
      <p className="px-2 py-1.5 text-sm font-medium" role="status">
        Validation · {issues.length} problem{issues.length === 1 ? "" : "s"}
      </p>
      <ul className="flex max-h-72 flex-col overflow-y-auto">
        {issues.map((issue, i) => (
          <li key={i}>
            <button
              type="button"
              disabled={!issue.node_id}
              onClick={() => {
                if (!issue.node_id) return;
                configureNode(issue.node_id);
                onPick();
              }}
              className="flex w-full items-start gap-2.5 rounded-lg px-2 py-2 text-left text-sm hover:bg-muted disabled:cursor-default disabled:hover:bg-transparent"
            >
              <CircleAlert className="mt-0.5 size-4 shrink-0 text-red-700 dark:text-red-400" aria-hidden />
              <span className="min-w-0">
                <span className="block font-medium">{nameOf(issue)}</span>
                <span className="block text-xs text-muted-foreground">{issue.message}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
      <p className="px-2 pt-1.5 pb-1 text-xs text-muted-foreground">
        Click a problem to select the node. Run is blocked until these are fixed.
      </p>
    </div>
  );
}
