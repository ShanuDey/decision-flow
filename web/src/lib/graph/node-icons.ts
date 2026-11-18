import { Flag, GitBranch, Globe, type LucideIcon, Play, Variable, Workflow } from "lucide-react";

import type { NodeType } from "./types";

export const NODE_ICONS: Record<NodeType, LucideIcon> = {
  start: Play,
  assign: Variable,
  condition: GitBranch,
  http_request: Globe,
  subflow: Workflow,
  end: Flag,
};
