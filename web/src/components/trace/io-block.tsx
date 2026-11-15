"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";

export type Format = "pretty" | "json";

const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);

const json = (v: unknown) => JSON.stringify(v, null, 2) ?? "null";

function CopyButton({ value }: { value: unknown }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);
  async function copy() {
    try {
      await navigator.clipboard.writeText(json(value));
      setCopied(true);
      clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 1200);
    } catch {
      // clipboard blocked: nothing to fall back to in a button
    }
  }
  return (
    <Button type="button" variant="ghost" size="xs" onClick={() => void copy()}>
      {copied ? "Copied" : "Copy"}
    </Button>
  );
}

function Pretty({ value }: { value: unknown }) {
  if (!isRecord(value)) {
    return <p className="font-mono text-xs break-words whitespace-pre-wrap">{typeof value === "string" ? value : json(value)}</p>;
  }
  const entries = Object.entries(value);
  if (entries.length === 0) return <p className="text-xs text-muted-foreground">Empty</p>;
  return (
    <dl className="divide-y text-xs">
      {entries.map(([key, v]) => (
        <div key={key} className="grid grid-cols-[6rem_minmax(0,1fr)] gap-2 py-1.5">
          <dt className="text-muted-foreground">{key}</dt>
          <dd className="min-w-0 break-words">
            {typeof v === "object" && v !== null ? (
              <pre className="overflow-auto rounded bg-muted p-2 font-mono">{json(v)}</pre>
            ) : (
              String(v)
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function IoBlock({
  title,
  value,
  format,
  footer,
}: {
  title: string;
  value: unknown;
  format: Format;
  footer?: React.ReactNode;
}) {
  const empty = value === null || value === undefined;
  return (
    <div className="min-w-0">
      <div className="mb-1 flex items-center justify-between">
        <h4 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">{title}</h4>
        {!empty && <CopyButton value={value} />}
      </div>
      {empty ? (
        <p className="text-xs text-muted-foreground">None</p>
      ) : format === "json" ? (
        <pre className="max-h-48 overflow-auto rounded-md bg-muted p-2 font-mono text-xs">{json(value)}</pre>
      ) : (
        <Pretty value={value} />
      )}
      {footer}
    </div>
  );
}
