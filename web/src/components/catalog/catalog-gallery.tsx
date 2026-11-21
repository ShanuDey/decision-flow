"use client";

import {
  Braces,
  ExternalLink,
  KeyRound,
  type LucideIcon,
  Plug,
  Search,
  Sparkles,
  UserRound,
  Workflow,
} from "lucide-react";
import { type ReactNode, useState } from "react";

import { DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { type CatalogItem, filterItems, groupItems } from "@/lib/catalog";

const ICONS: Record<string, LucideIcon> = {
  sparkles: Sparkles,
  "key-round": KeyRound,
  "user-round": UserRound,
  braces: Braces,
  workflow: Workflow,
};

export function CatalogIcon({ name, className }: { name: string; className?: string }) {
  const Icon = ICONS[name] ?? Plug;
  return <Icon className={className} aria-hidden />;
}

function Card({ item, onPick }: { item: CatalogItem; onPick: () => void }) {
  return (
    <div className="flex flex-col rounded-lg border focus-within:ring-2 focus-within:ring-ring/50 hover:border-foreground/30">
      <button
        type="button"
        onClick={onPick}
        className="flex flex-1 items-start gap-3 rounded-lg p-3 text-left outline-none"
      >
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted">
          <CatalogIcon name={item.icon} className="size-4" />
        </span>
        <span className="flex min-w-0 flex-col gap-0.5">
          <span className="text-sm font-medium">{item.name}</span>
          <span className="text-xs text-muted-foreground">{item.description}</span>
        </span>
      </button>
      {item.docsUrl && (
        <a
          href={item.docsUrl}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1 px-3 pb-2 pl-15 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
        >
          Docs <ExternalLink className="size-3" aria-hidden />
        </a>
      )}
    </div>
  );
}

export function CatalogGallery({
  title,
  description,
  items,
  order,
  onPick,
  footer,
}: {
  title: string;
  description: string;
  items: CatalogItem[];
  order: string[];
  onPick: (id: string) => void;
  footer?: ReactNode;
}) {
  const [query, setQuery] = useState("");
  const sections = groupItems(filterItems(items, query), order);

  return (
    <div className="flex flex-col gap-4">
      <DialogHeader>
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription>{description}</DialogDescription>
      </DialogHeader>
      <div className="flex h-9 items-center gap-2 rounded-lg border border-input px-2.5 focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50">
        <Search className="size-3.5 text-muted-foreground" aria-hidden />
        <input
          aria-label={`Search ${title.toLowerCase()}`}
          placeholder="Search"
          value={query}
          autoFocus
          onChange={(e) => setQuery(e.target.value)}
          className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        />
      </div>
      <div className="flex max-h-[min(420px,55vh)] flex-col gap-4 overflow-y-auto">
        {sections.length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">Nothing matches your search.</p>
        )}
        {sections.map((section) => (
          <div key={section.label} role="group" aria-label={section.label} className="flex flex-col gap-2">
            <p className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
              {section.label}
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {section.items.map((item) => (
                <Card key={item.id} item={item} onPick={() => onPick(item.id)} />
              ))}
            </div>
          </div>
        ))}
      </div>
      {footer}
    </div>
  );
}
