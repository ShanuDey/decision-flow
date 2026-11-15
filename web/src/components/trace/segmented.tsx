"use client";

import { cn } from "@/lib/utils";

export function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex overflow-hidden rounded-md border text-xs">
      {options.map((option, i) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={cn(
            "px-2.5 py-1 text-muted-foreground outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
            i > 0 && "border-l",
            value === option.value && "bg-muted font-medium text-foreground",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
