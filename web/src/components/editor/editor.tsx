"use client";

import { ReactFlowProvider } from "@xyflow/react";
import { useEffect, useState } from "react";

import type { Graph } from "@/lib/graph/types";

import type { RunOutcome } from "./actions";
import { Canvas } from "./canvas";
import { Palette } from "./palette";
import { RunPanel } from "./run-panel";
import { SettingsPanel } from "./settings-panel";
import { useEditor } from "./store";
import { TopBar } from "./top-bar";

export interface EditorProps {
  id: string;
  name: string;
  draftVersion: number;
  graph: Graph;
}

export default function Editor({ id, name, draftVersion, graph }: EditorProps) {
  // Runs once, before the first render of the children (this component is client-only).
  useState(() => useEditor.getState().load({ id, name, draftVersion, graph }));
  const [outcome, setOutcome] = useState<RunOutcome | null>(null);
  const dirty = useEditor((s) => s.dirty);

  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  return (
    <div className="flex h-screen flex-col">
      <TopBar onOutcome={setOutcome} />
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <Palette />
        <div className="flex min-h-[320px] min-w-0 flex-1 flex-col">
          <ReactFlowProvider>
            <Canvas />
          </ReactFlowProvider>
          {outcome && <RunPanel outcome={outcome} onClose={() => setOutcome(null)} />}
        </div>
        <SettingsPanel />
      </div>
    </div>
  );
}
