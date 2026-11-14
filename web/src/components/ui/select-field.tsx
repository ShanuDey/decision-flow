"use client";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

export type SelectOption = { value: string; label: string };

// Base UI items can't be reliably keyed by "", so the empty value is mapped to a sentinel.
const EMPTY = "__empty__";
const toItem = (v: string) => (v === "" ? EMPTY : v);

export function SelectField({
  id,
  value,
  onValueChange,
  options,
  placeholder,
  className,
}: {
  id?: string;
  value: string;
  onValueChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  className?: string;
}) {
  const items = options.map((o) => ({ value: toItem(o.value), label: o.label }));
  return (
    <Select
      items={items}
      value={value === "" && !options.some((o) => o.value === "") ? null : toItem(value)}
      onValueChange={(v) => onValueChange(v === null || v === EMPTY ? "" : v)}
    >
      <SelectTrigger id={id} className={cn("h-10 w-full", className)}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent alignItemWithTrigger={false}>
        {items.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
