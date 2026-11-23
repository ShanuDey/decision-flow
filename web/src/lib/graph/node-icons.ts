import { Bot, Braces, Flag, GitBranch, Globe, type LucideIcon, Play, Sparkles, Variable, Workflow } from "lucide-react";

import type { NodeType } from "./types";

export const NODE_ICONS: Record<NodeType, LucideIcon> = {
  start: Play,
  assign: Variable,
  condition: GitBranch,
  http_request: Globe,
  prompt: Sparkles,
  structured_output: Braces,
  agent: Bot,
  subflow: Workflow,
  end: Flag,
};
