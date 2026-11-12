"use client";

import { useMemo, useRef, useState } from "react";

import { Input } from "@/components/ui/input";
import { fromReactFlow } from "@/lib/graph/convert";
import { suggest } from "@/lib/graph/suggest";
import { cn } from "@/lib/utils";

import { useEditor } from "./store";

interface Props {
  id: string;
  nodeId: string;
  value: string;
  placeholder?: string;
  onChange: (value: string) => void;
}

export function ExpressionInput({ id, nodeId, value, placeholder, onChange }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [cursor, setCursor] = useState(value.length);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);

  // read on demand: subscribing to the store would re-render this field on every node drag
  const { from, items } = useMemo(() => {
    if (!open) return { from: 0, items: [] };
    const { nodes, edges, variables } = useEditor.getState();
    return suggest(fromReactFlow({ nodes, edges, variables }), nodeId, value, cursor);
  }, [open, nodeId, value, cursor]);
  const showing = open && items.length > 0;
  const current = Math.min(active, items.length - 1);

  const accept = (i: number) => {
    const item = items[i];
    if (!item) return;
    const next = value.slice(0, from) + item.insert + value.slice(cursor);
    const end = from + item.insert.length;
    onChange(next);
    setCursor(end);
    setActive(0);
    requestAnimationFrame(() => input.current?.setSelectionRange(end, end));
  };

  const track = (el: HTMLInputElement) => setCursor(el.selectionStart ?? el.value.length);

  return (
    <div className="relative">
      <Input
        id={id}
        ref={input}
        className="h-10 font-mono text-xs"
        value={value}
        placeholder={placeholder}
        autoComplete="off"
        spellCheck={false}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={showing}
        aria-controls={showing ? `${id}-suggestions` : undefined}
        aria-activedescendant={showing ? `${id}-option-${current}` : undefined}
        onChange={(e) => {
          onChange(e.target.value);
          track(e.target);
          setOpen(true);
          setActive(0);
        }}
        onClick={(e) => track(e.currentTarget)}
        onFocus={(e) => track(e.currentTarget)}
        onBlur={() => setOpen(false)}
        onKeyUp={(e) => {
          if (e.key === "ArrowLeft" || e.key === "ArrowRight" || e.key === "Home" || e.key === "End")
            track(e.currentTarget);
        }}
        onKeyDown={(e) => {
          if (e.ctrlKey && e.key === " ") {
            e.preventDefault();
            setOpen(true);
            return;
          }
          if (!showing) return;
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            const step = e.key === "ArrowDown" ? 1 : -1;
            setActive((current + step + items.length) % items.length);
          } else if (e.key === "Enter" || e.key === "Tab") {
            e.preventDefault();
            accept(current);
          } else if (e.key === "Escape") {
            e.preventDefault();
            e.stopPropagation();
            setOpen(false);
          }
        }}
      />
      {showing && (
        <ul
          id={`${id}-suggestions`}
          role="listbox"
          className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-lg border bg-popover p-1 text-popover-foreground shadow-md"
        >
          {items.map((item, i) => (
            <li
              key={item.insert}
              id={`${id}-option-${i}`}
              role="option"
              aria-selected={i === current}
              className={cn(
                "flex cursor-pointer items-baseline justify-between gap-3 rounded-md px-2 py-1.5 font-mono text-xs",
                i === current && "bg-accent text-accent-foreground",
              )}
              onMouseDown={(e) => {
                e.preventDefault();
                accept(i);
              }}
              onMouseEnter={() => setActive(i)}
            >
              <span className="truncate">{item.label}</span>
              <span className="shrink-0 font-sans text-muted-foreground">{item.detail}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
