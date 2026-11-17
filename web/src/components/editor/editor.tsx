"use client";

import { ReactFlowProvider } from "@xyflow/react";
import { useEffect, useState } from "react";

import { config as getConfig, listSecrets } from "@/lib/api/client";
import { call } from "@/lib/call";
import { limitsOf } from "@/lib/graph/limits";
import { calledFlowIds } from "@/lib/graph/subflow";
import type { Graph } from "@/lib/graph/types";

import type { RunOutcome } from "./actions";
import { Canvas } from "./canvas";
import { LeaveDialog } from "./leave-guard";
import { RunPanel } from "./run-panel";
import { SettingsPanel } from "./settings-panel";
import type { PublishedInfo } from "./published";
import { useEditor } from "./store";
import { ensureContracts, loadPublishedFlows } from "./subflows";
import { TopBar } from "./top-bar";
import { VariablesDialog } from "./variables-dialog";

export interface EditorProps {
  id: string;
  name: string;
  draftVersion: number;
  graph: Graph;
  published: PublishedInfo | null;
}

export default function Editor({ id, name, draftVersion, graph, published }: EditorProps) {
  // Runs once, before the first render of the children (this component is client-only).
  useState(() => useEditor.getState().load({ id, name, draftVersion, graph, published }));
  const [outcome, setOutcome] = useState<RunOutcome | null>(null);
  const dirty = useEditor((s) => s.dirty);

  useEffect(() => {
    let stale = false;
    call(listSecrets()).then((result) => {
      if (stale || !result.ok) return;
      useEditor.getState().setSecretNames(result.data.items.map((item) => item.name));
    });
    call(getConfig()).then((result) => {
      if (stale || !result.ok) return;
      useEditor.getState().setLimits(limitsOf(result.data));
    });
    return () => {
      stale = true;
    };
  }, []);

  useEffect(() => {
    let stale = false;
    loadPublishedFlows().then((page) => {
      if (stale || !page) return;
      useEditor.getState().setPublishedFlows(page.flows, page.more);
    });
    void ensureContracts(calledFlowIds(graph));
    return () => {
      stale = true;
    };
    // the flow is loaded once; later picks load their own contracts
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
        <div className="flex min-h-[320px] min-w-0 flex-1 flex-col">
          <ReactFlowProvider>
            <Canvas />
          </ReactFlowProvider>
          {outcome && <RunPanel outcome={outcome} onClose={() => setOutcome(null)} />}
        </div>
        <SettingsPanel />
      </div>
      <VariablesDialog />
      <LeaveDialog />
    </div>
  );
}
