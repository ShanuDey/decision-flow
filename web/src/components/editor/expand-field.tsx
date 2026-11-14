"use client";

import { Maximize2 } from "lucide-react";
import dynamic from "next/dynamic";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import type { SourceKind } from "./expand-dialog";

// CodeMirror only loads when a field is first expanded.
const ExpandDialog = dynamic(() => import("./expand-dialog"), { ssr: false });

interface Props {
  nodeId: string;
  title: string;
  kind: SourceKind;
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

export function ExpandButton({ nodeId, title, kind, value, onChange, className }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="icon-sm"
        className={className}
        aria-label={`Expand ${title} editor`}
        title="Expand editor"
        onClick={() => setOpen(true)}
      >
        <Maximize2 aria-hidden />
      </Button>
      {open && (
        <ExpandDialog
          open={open}
          onOpenChange={setOpen}
          nodeId={nodeId}
          title={title}
          kind={kind}
          value={value}
          onChange={onChange}
        />
      )}
    </>
  );
}

interface InputProps extends Omit<Props, "kind" | "className"> {
  id: string;
  placeholder?: string;
}

export function ExpandableInput({ id, nodeId, title, value, placeholder, onChange }: InputProps) {
  return (
    <div className="relative">
      <Input
        id={id}
        className="h-10 pr-10 font-mono text-xs"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
      <ExpandButton
        nodeId={nodeId}
        title={title}
        kind="template"
        value={value}
        onChange={onChange}
        className="absolute top-1/2 right-1.5 -translate-y-1/2"
      />
    </div>
  );
}
