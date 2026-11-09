"use client";

import { CircleAlert, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import type { FieldIssue } from "@/lib/call";
import { FIELD_TYPES, type FieldType } from "@/lib/graph/types";

export function FieldError({ issue }: { issue?: FieldIssue }) {
  if (!issue) return null;
  return (
    <p role="alert" className="flex items-start gap-1.5 text-xs text-red-700 dark:text-red-400">
      <CircleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
      {issue.message}
    </p>
  );
}

export function Labeled({
  id,
  label,
  issue,
  children,
}: {
  id: string;
  label: string;
  issue?: FieldIssue;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id} className="text-xs text-muted-foreground">
        {label}
      </Label>
      {children}
      <FieldError issue={issue} />
    </div>
  );
}

export function TypeSelect({
  id,
  value,
  onChange,
}: {
  id: string;
  value: FieldType;
  onChange: (type: FieldType) => void;
}) {
  return (
    <NativeSelect id={id} value={value} onChange={(e) => onChange(e.target.value as FieldType)}>
      {FIELD_TYPES.map((t) => (
        <option key={t} value={t}>
          {t}
        </option>
      ))}
    </NativeSelect>
  );
}

// Comma-separated enum values. The text being typed lives in `draft` only while the field is
// focused, so rows that shift after a removal never show another row's stale text.
export function EnumValues({
  id,
  values,
  onChange,
}: {
  id: string;
  values: string[] | undefined;
  onChange: (values: string[]) => void;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  return (
    <Input
      id={id}
      className="h-10"
      value={draft ?? (values ?? []).join(", ")}
      placeholder="silver, gold"
      onChange={(e) => {
        setDraft(e.target.value);
        onChange(
          e.target.value
            .split(",")
            .map((v) => v.trim())
            .filter(Boolean),
        );
      }}
      onBlur={() => setDraft(null)}
    />
  );
}

// Edits a value of a declared type; `undefined` means "not set".
export function TypedValueInput({
  id,
  type,
  values,
  value,
  onChange,
}: {
  id: string;
  type: FieldType;
  values?: string[];
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  // Typed text is kept only while it is being edited or invalid; otherwise show the real value.
  const [draft, setDraft] = useState<string | null>(null);
  const [jsonError, setJsonError] = useState(false);
  const json = draft ?? (value === undefined || value === null ? "" : JSON.stringify(value));

  switch (type) {
    case "boolean":
      return (
        <NativeSelect
          id={id}
          value={value === true ? "true" : value === false ? "false" : ""}
          onChange={(e) => onChange(e.target.value === "" ? undefined : e.target.value === "true")}
        >
          <option value="">(none)</option>
          <option value="true">true</option>
          <option value="false">false</option>
        </NativeSelect>
      );
    case "enum":
      return (
        <NativeSelect
          id={id}
          value={typeof value === "string" ? value : ""}
          onChange={(e) => onChange(e.target.value === "" ? undefined : e.target.value)}
        >
          <option value="">(none)</option>
          {(values ?? []).map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </NativeSelect>
      );
    case "number":
      return (
        <Input
          id={id}
          type="number"
          className="h-10"
          value={typeof value === "number" ? value : ""}
          onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))}
        />
      );
    case "object":
    case "array":
      return (
        <>
          <Textarea
            id={id}
            className="font-mono text-xs"
            rows={2}
            value={json}
            aria-invalid={jsonError}
            placeholder={type === "object" ? "{}" : "[]"}
            onBlur={() => {
              if (!jsonError) setDraft(null);
            }}
            onChange={(e) => {
              setDraft(e.target.value);
              if (e.target.value.trim() === "") {
                setJsonError(false);
                onChange(undefined);
                return;
              }
              try {
                onChange(JSON.parse(e.target.value));
                setJsonError(false);
              } catch {
                setJsonError(true);
              }
            }}
          />
          {jsonError && <FieldError issue={{ code: "json", message: "Not valid JSON", node_id: null, field: null }} />}
        </>
      );
    default:
      return (
        <Input
          id={id}
          className="h-10"
          value={typeof value === "string" ? value : ""}
          onChange={(e) => onChange(e.target.value === "" ? undefined : e.target.value)}
        />
      );
  }
}

// A titled list with add/remove, used by every node's settings.
export function ListEditor<T>({
  title,
  items,
  addLabel,
  emptyText,
  onAdd,
  onRemove,
  renderItem,
}: {
  title: string;
  items: T[];
  addLabel: string;
  emptyText: string;
  onAdd: () => void;
  onRemove: (index: number) => void;
  renderItem: (item: T, index: number) => React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <h3 className="text-sm font-medium">{title}</h3>
      {items.length === 0 && <p className="text-xs text-muted-foreground">{emptyText}</p>}
      {items.map((item, i) => (
        <div key={i} className="flex flex-col gap-3 rounded-lg border p-3">
          {renderItem(item, i)}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="self-end"
            onClick={() => onRemove(i)}
          >
            <Trash2 aria-hidden /> Remove
            <span className="sr-only"> {title.toLowerCase()} item {i + 1}</span>
          </Button>
        </div>
      ))}
      <Button type="button" variant="outline" className="h-10" onClick={onAdd}>
        <Plus aria-hidden /> {addLabel}
      </Button>
    </section>
  );
}
