import { Flag, GitBranch, type LucideIcon, Play, Variable } from "lucide-react";

import type { NodeType } from "./types";

export const NODE_ICONS: Record<NodeType, LucideIcon> = {
  start: Play,
  assign: Variable,
  condition: GitBranch,
  end: Flag,
};
