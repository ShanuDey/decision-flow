"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { evaluateExpression } from "@/lib/api/client";
import { call, errorText } from "@/lib/call";
import { fromReactFlow } from "@/lib/graph/convert";
import { availableData, sampleScope } from "@/lib/graph/scope";
import { cn } from "@/lib/utils";

import { useEditor } from "./store";

interface Props {
  nodeId: string;
  kind: "expression" | "template";
  source: string;
  idPrefix: string;
}

export function TestPane({ nodeId, kind, source, idPrefix }: Props) {
  // Read on demand so "Reset sample" sees inputs added since this pane opened.
  const freshSample = () => {
    const { nodes, edges, variables } = useEditor.getState();
    return sampleScope(availableData(fromReactFlow({ nodes, edges, variables }), nodeId));
  };
  const [sample, setSample] = useState(freshSample);
  const [outcome, setOutcome] = useState<{ ok: boolean; text: string } | null>(null);
  const [running, setRunning] = useState(false);

  async function run() {
    let scope: Record<string, unknown>;
    try {
      scope = JSON.parse(sample);
    } catch {
      setOutcome({ ok: false, text: "The sample input is not valid JSON." });
      return;
    }
    setRunning(true);
    const result = await call(evaluateExpression({ kind, source, scope }));
    setRunning(false);
    if (!result.ok) setOutcome({ ok: false, text: errorText(result.error) });
    else if (!result.data.valid) setOutcome({ ok: false, text: result.data.error ?? "Invalid" });
    else setOutcome({ ok: true, text: JSON.stringify(result.data.result) });
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center">
        <p className="flex-1 text-[11px] font-semibold tracking-wider text-muted-foreground">TEST</p>
        <Button size="sm" variant="outline" onClick={() => void run()} disabled={running}>
          {running ? "Running…" : "Run test"}
        </Button>
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center">
          <label htmlFor={`${idPrefix}-sample`} className="flex-1 text-xs font-semibold">
            Sample input
          </label>
          <Button size="xs" variant="ghost" onClick={() => setSample(freshSample())}>
            Reset sample
          </Button>
        </div>
        <textarea
          id={`${idPrefix}-sample`}
          value={sample}
          spellCheck={false}
          onChange={(e) => setSample(e.target.value)}
          className="h-44 resize-none rounded-lg border bg-muted/30 p-2 font-mono text-xs outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <p className="text-xs font-semibold">Result</p>
        {outcome ? (
          <p
            data-testid="test-result"
            className={cn(
              "rounded-lg border p-2 font-mono text-xs break-words",
              outcome.ok
                ? "border-green-300 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950/40 dark:text-green-300"
                : "border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300",
            )}
          >
            {outcome.text}
          </p>
        ) : (
          <p className="text-xs text-muted-foreground">Run a test to see the result.</p>
        )}
      </div>
    </div>
  );
}
