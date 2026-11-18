import type { AppConfig } from "@/lib/api/models";
import { type LimitNotice, noticeFrom } from "@/lib/call";

export interface EditorLimits {
  disabledNodeTypes: string[];
  maxNodes: number;
  maxEdges: number;
  notice: LimitNotice | null;
}

// Used until the server answers, or when it cannot: the server still enforces its own limits.
export const NO_LIMITS: EditorLimits = {
  disabledNodeTypes: [],
  maxNodes: 0,
  maxEdges: 0,
  notice: null,
};

// 0 means no limit.
export const atLimit = (count: number, max: number): boolean => max > 0 && count >= max;

export const nearLimit = (count: number, max: number): boolean => max > 0 && count >= Math.ceil(max * 0.8);

export function limitsOf(config: AppConfig): EditorLimits {
  return {
    disabledNodeTypes: config.disabled_node_types,
    maxNodes: config.max_nodes,
    maxEdges: config.max_edges,
    notice: noticeFrom(config.limit_notice, config.limit_notice_url),
  };
}
