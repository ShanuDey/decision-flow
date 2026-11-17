"use client";

import { nearLimit } from "@/lib/graph/limits";

import { useEditor } from "./store";

// Shown only once a flow is close to a server limit, with the operator's notice if there is one.
export function LimitHint() {
  const nodes = useEditor((s) => s.nodes.length);
  const edges = useEditor((s) => s.edges.length);
  const { maxNodes, maxEdges, notice } = useEditor((s) => s.limits);
  const parts = [
    nearLimit(nodes, maxNodes) && `${nodes} of ${maxNodes} nodes`,
    nearLimit(edges, maxEdges) && `${edges} of ${maxEdges} connections`,
  ].filter(Boolean);
  if (parts.length === 0) return null;
  return (
    <p role="status" className="text-xs text-muted-foreground">
      {parts.join(" · ")}
      {notice && (
        <>
          {" · "}
          {notice.url ? (
            <a href={notice.url} target="_blank" rel="noreferrer" className="underline">
              {notice.text}
            </a>
          ) : (
            notice.text
          )}
        </>
      )}
    </p>
  );
}
