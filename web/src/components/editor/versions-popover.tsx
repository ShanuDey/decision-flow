"use client";

import { useEffect, useState } from "react";

import type { VersionList } from "@/lib/api/models";
import { listVersions } from "@/lib/api/client";
import { call, errorText } from "@/lib/call";
import { formatDateTime } from "@/lib/format";

import { keepNote } from "./published";
import { useEditor } from "./store";

type State = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; list: VersionList };

export function VersionsList() {
  const flowId = useEditor((s) => s.flowId);
  // Publishing changes the list, so reload when the latest version moves.
  const latest = useEditor((s) => s.publishedVersion);
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    void call(listVersions(flowId, { cache: "no-store" })).then((result) => {
      if (cancelled) return;
      setState(
        result.ok
          ? { kind: "ready", list: result.data }
          : { kind: "error", message: errorText(result.error) },
      );
    });
    return () => {
      cancelled = true;
    };
  }, [flowId, latest]);

  if (state.kind === "loading") {
    return <p className="p-3 text-sm text-muted-foreground">Loading versions…</p>;
  }
  if (state.kind === "error") {
    return (
      <p role="alert" className="p-3 text-sm text-red-700 dark:text-red-400">
        Could not load versions: {state.message}
      </p>
    );
  }

  const note = keepNote(state.list.keep_latest);
  return (
    <div className="p-2">
      <p className="px-2 py-1.5 text-sm font-medium">Versions</p>
      <ul className="flex max-h-72 flex-col overflow-y-auto">
        {state.list.items.map((version, i) => (
          <li key={version.version} className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm">
            <span className="font-medium">v{version.version}</span>
            {i === 0 && (
              <span className="rounded-full bg-muted px-1.5 text-[11px] text-muted-foreground">
                current
              </span>
            )}
            <span className="ml-auto text-xs text-muted-foreground">
              {formatDateTime(version.created_at)}
            </span>
          </li>
        ))}
      </ul>
      {note && <p className="px-2 pt-1.5 pb-1 text-xs text-muted-foreground">{note}</p>}
    </div>
  );
}
