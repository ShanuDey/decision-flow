"use client";

import { Search, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import type { ThreadSummary } from "@/lib/api/models";
import { groupByDay } from "@/lib/agents";
import { cn } from "@/lib/utils";

// Searchable conversations grouped by day; pass `onDelete` to offer a two-click delete.
export function ThreadList({
  threads,
  activeId,
  onOpen,
  onDelete,
  className,
}: {
  threads: ThreadSummary[];
  activeId: string | null;
  onOpen: (id: string) => void;
  onDelete?: (id: string) => Promise<void>;
  className?: string;
}) {
  const [query, setQuery] = useState("");
  const [confirming, setConfirming] = useState<string | null>(null);

  const groups = useMemo(() => {
    const term = query.trim().toLowerCase();
    const shown = term ? threads.filter((t) => (t.title || "New chat").toLowerCase().includes(term)) : threads;
    return groupByDay(shown);
  }, [threads, query]);

  return (
    <div className={cn("flex min-h-0 flex-col gap-2", className)}>
      <label className="flex h-9 shrink-0 items-center gap-2 rounded-lg bg-muted/60 px-3 text-muted-foreground focus-within:ring-3 focus-within:ring-ring/40">
        <Search className="size-4 shrink-0" aria-hidden />
        <input
          type="search"
          aria-label="Search chats"
          placeholder="Search chats"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full min-w-0 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
        />
      </label>
      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto">
        {threads.length === 0 && <p className="px-2 py-1 text-xs text-muted-foreground">No conversations yet.</p>}
        {threads.length > 0 && groups.length === 0 && (
          <p className="px-2 py-1 text-xs text-muted-foreground">No chats match.</p>
        )}
        {groups.map((group) => (
          <section key={group.label} aria-label={group.label} className="flex flex-col gap-0.5">
            <h3 className="px-2 pb-1 text-xs font-medium text-muted-foreground">{group.label}</h3>
            <ul className="flex flex-col gap-0.5">
              {group.items.map((thread) => (
                <li key={thread.id} className="group relative">
                  <button
                    type="button"
                    aria-current={thread.id === activeId ? "true" : undefined}
                    onClick={() => {
                      setConfirming(null);
                      onOpen(thread.id);
                    }}
                    className={cn(
                      "block w-full min-w-0 rounded-lg px-2.5 py-2 text-left text-sm outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50",
                      onDelete && "pr-16",
                      thread.id === activeId && "bg-muted font-medium",
                    )}
                  >
                    <span className="block truncate">{thread.title || "New chat"}</span>
                  </button>
                  {onDelete && (
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={confirming === thread.id ? "Confirm delete" : "Delete conversation"}
                      className={cn(
                        "absolute right-1 top-1/2 h-7 -translate-y-1/2 px-1.5 opacity-0 focus-visible:opacity-100 group-focus-within:opacity-100 group-hover:opacity-100",
                        confirming === thread.id && "text-red-700 opacity-100 dark:text-red-400",
                      )}
                      onClick={() => {
                        if (confirming !== thread.id) {
                          setConfirming(thread.id);
                          return;
                        }
                        setConfirming(null);
                        void onDelete(thread.id);
                      }}
                    >
                      {confirming === thread.id ? "Delete?" : <Trash2 aria-hidden />}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
