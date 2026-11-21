import { Flag, GitBranch, Globe, type LucideIcon, Play, Sparkles, Variable, Workflow } from "lucide-react";

import type { NodeType } from "./types";

export const NODE_ICONS: Record<NodeType, LucideIcon> = {
  start: Play,
  assign: Variable,
  condition: GitBranch,
  http_request: Globe,
  prompt: Sparkles,
  subflow: Workflow,
  end: Flag,
};
