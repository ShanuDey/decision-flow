import { Flag, GitBranch, Globe, type LucideIcon, Play, Variable } from "lucide-react";

import type { NodeType } from "./types";

export const NODE_ICONS: Record<NodeType, LucideIcon> = {
  start: Play,
  assign: Variable,
  condition: GitBranch,
  http_request: Globe,
  end: Flag,
};
