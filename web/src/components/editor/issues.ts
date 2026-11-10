import type { FieldIssue } from "@/lib/call";

export const issuesForNode = (issues: FieldIssue[], nodeId: string) =>
  issues.filter((i) => i.node_id === nodeId);

// Backend fields are either relative ("data.assignments.0.variable") or full
// ("nodes.1.data.assignments.0.variable") depending on the validation stage.
export function fieldIssue(
  issues: FieldIssue[],
  nodeId: string,
  field: string,
): FieldIssue | undefined {
  return issues.find(
    (i) => i.node_id === nodeId && i.field && (i.field === field || i.field.endsWith(`.${field}`)),
  );
}

export const flowIssues = (issues: FieldIssue[]) => issues.filter((i) => i.node_id === null);
