"use client";

import { ArrowLeft, RefreshCw, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { CatalogIcon } from "@/components/catalog/catalog-gallery";
import { Markdown } from "@/components/catalog/markdown";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  getCatalogIndex,
  getCatalogReadme,
  installItem,
  listInstalled,
  refreshCatalogIndex,
  uninstallItem,
} from "@/lib/api/client";
import type { CatalogListing, InstalledSummary } from "@/lib/api/models";
import { errorToast } from "@/lib/api-error";
import { call, errorText } from "@/lib/call";
import {
  filterEntries,
  installBody,
  joinCatalog,
  KIND_LABELS,
  type Kind,
  type MarketEntry,
  relativeTime,
} from "@/lib/marketplace";
import { cn } from "@/lib/utils";

type Loaded =
  | { state: "loading" }
  | { state: "error"; message: string; unavailable: boolean }
  | { state: "ready"; listing: CatalogListing; installed: InstalledSummary[] };

const FILTERS: { label: string; kinds: Kind[] | null }[] = [
  { label: "All", kinds: null },
  { label: "Connections", kinds: ["connection-type"] },
  { label: "Templates", kinds: ["node-template"] },
];

function sameKinds(a: Kind[] | null, b: Kind[] | null): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

function versionLabel(entry: MarketEntry): string {
  return entry.status === "update" && entry.installedVersion !== entry.version
    ? `v${entry.installedVersion} → v${entry.version}`
    : `v${entry.version}`;
}

function Actions({
  entry,
  busy,
  onInstall,
  onRemove,
}: {
  entry: MarketEntry;
  busy: boolean;
  onInstall: () => void;
  onRemove: () => void;
}) {
  return (
    <span className="flex gap-1">
      {entry.status !== "available" && (
        <Button type="button" variant="ghost" size="sm" disabled={busy} onClick={onRemove}>
          Remove
        </Button>
      )}
      <Button
        type="button"
        size="sm"
        variant={entry.status === "available" || entry.status === "update" ? "default" : "outline"}
        disabled={busy || entry.status === "installed"}
        onClick={onInstall}
      >
        {entry.status === "installed" ? "Installed" : entry.status === "update" ? "Update" : "Install"}
      </Button>
    </span>
  );
}

function Card({
  entry,
  busy,
  onInstall,
  onRemove,
  onDetails,
}: {
  entry: MarketEntry;
  busy: boolean;
  onInstall: () => void;
  onRemove: () => void;
  onDetails: () => void;
}) {
  return (
    <li className="flex flex-col gap-3 rounded-lg border p-3">
      <div className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted">
          <CatalogIcon name={entry.icon ?? "plug"} className="size-4" />
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium">{entry.name}</span>
            <Badge variant="secondary">{KIND_LABELS[entry.kind]}</Badge>
          </span>
          <span className="text-xs text-muted-foreground">{entry.description}</span>
        </div>
      </div>
      {entry.alsoInstalls.length > 0 && (
        <p className="text-xs text-muted-foreground">Also installs {entry.alsoInstalls.join(", ")}.</p>
      )}
      <div className="mt-auto flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-xs text-muted-foreground">
          {versionLabel(entry)}
          {entry.has_readme && (
            <button
              type="button"
              className="underline underline-offset-2 hover:text-foreground"
              aria-label={`Details of ${entry.name}`}
              onClick={onDetails}
            >
              Details
            </button>
          )}
        </span>
        <Actions entry={entry} busy={busy} onInstall={onInstall} onRemove={onRemove} />
      </div>
    </li>
  );
}

type Notes = { state: "loading" } | { state: "error"; message: string } | { state: "ready"; markdown: string };

function Detail({
  entry,
  busy,
  onBack,
  onInstall,
  onRemove,
}: {
  entry: MarketEntry;
  busy: boolean;
  onBack: () => void;
  onInstall: () => void;
  onRemove: () => void;
}) {
  const [notes, setNotes] = useState<Notes>({ state: "loading" });

  useEffect(() => {
    let stale = false;
    call(getCatalogReadme(entry.kind, entry.id)).then((result) => {
      if (stale) return;
      setNotes(
        result.ok ? { state: "ready", markdown: result.data.markdown } : { state: "error", message: errorText(result.error) },
      );
    });
    return () => {
      stale = true;
    };
  }, [entry.kind, entry.id]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft aria-hidden /> All items
        </Button>
        <Actions entry={entry} busy={busy} onInstall={onInstall} onRemove={onRemove} />
      </div>
      <div className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted">
          <CatalogIcon name={entry.icon ?? "plug"} className="size-4" />
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-medium">{entry.name}</h3>
            <Badge variant="secondary">{KIND_LABELS[entry.kind]}</Badge>
            <span className="text-xs text-muted-foreground">{versionLabel(entry)}</span>
          </span>
          <span className="text-xs text-muted-foreground">{entry.description}</span>
          {entry.alsoInstalls.length > 0 && (
            <span className="text-xs text-muted-foreground">Also installs {entry.alsoInstalls.join(", ")}.</span>
          )}
        </div>
      </div>
      <div className="border-t pt-1">
        {notes.state === "loading" && (
          <p role="status" className="py-6 text-center text-sm text-muted-foreground">
            Loading details…
          </p>
        )}
        {notes.state === "error" && (
          <p role="alert" className="py-6 text-center text-sm text-muted-foreground">
            Could not load the details: {notes.message}
          </p>
        )}
        {notes.state === "ready" && <Markdown>{notes.markdown}</Markdown>}
      </div>
    </div>
  );
}

export function MarketplaceView({
  kinds: initialKinds,
  onChanged,
  className,
}: {
  kinds: Kind[] | null;
  onChanged?: () => void;
  className?: string;
}) {
  const [loaded, setLoaded] = useState<Loaded>({ state: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [query, setQuery] = useState("");
  const [kinds, setKinds] = useState<Kind[] | null>(initialKinds);
  const [busy, setBusy] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [detailKey, setDetailKey] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    let stale = false;
    Promise.all([call(getCatalogIndex()), call(listInstalled())]).then(([index, installed]) => {
      if (stale) return;
      if (!index.ok) {
        setLoaded({ state: "error", message: errorText(index.error), unavailable: index.error.status === 503 });
      } else if (!installed.ok) {
        setLoaded({ state: "error", message: errorText(installed.error), unavailable: false });
      } else {
        setNow(Date.now());
        setLoaded({ state: "ready", listing: index.data, installed: installed.data.items });
      }
    });
    return () => {
      stale = true;
    };
  }, [attempt]);

  async function refresh() {
    setRefreshing(true);
    const result = await call(refreshCatalogIndex());
    setRefreshing(false);
    if (!result.ok) {
      errorToast("Could not refresh the Marketplace", result.error);
      return;
    }
    setNow(Date.now());
    setLoaded((current) => (current.state === "ready" ? { ...current, listing: result.data } : current));
  }

  async function refreshInstalled() {
    const installed = await call(listInstalled());
    if (installed.ok) {
      setLoaded((current) => (current.state === "ready" ? { ...current, installed: installed.data.items } : current));
    }
  }

  async function install(entry: MarketEntry) {
    setBusy(`${entry.kind}/${entry.id}`);
    const result = await call(installItem(installBody(entry)));
    if (!result.ok) {
      setBusy(null);
      errorToast(`Could not install ${entry.name}`, result.error);
      if (result.error.code === "hash_mismatch") setAttempt((n) => n + 1);
      return;
    }
    const extra = result.data.installed.slice(1).map((i) => i.name);
    toast.success(extra.length ? `Installed ${entry.name} and ${extra.join(", ")}` : `Installed ${entry.name}`);
    await refreshInstalled();
    setBusy(null);
    onChanged?.();
  }

  async function remove(entry: MarketEntry) {
    setBusy(`${entry.kind}/${entry.id}`);
    const result = await call(uninstallItem(entry.kind, entry.id));
    if (!result.ok) {
      setBusy(null);
      errorToast(`Could not remove ${entry.name}`, result.error);
      return;
    }
    toast.success(`Removed ${entry.name}`);
    await refreshInstalled();
    setBusy(null);
    onChanged?.();
  }

  const market = useMemo(
    () => (loaded.state === "ready" ? joinCatalog(loaded.listing.entries, loaded.installed) : []),
    [loaded],
  );

  if (loaded.state !== "ready") {
    return (
      <p role={loaded.state === "error" ? "alert" : "status"} className="py-8 text-center text-sm text-muted-foreground">
        {loaded.state === "loading" ? (
          "Loading the Marketplace…"
        ) : (
          <>
            {loaded.unavailable ? (
              <>
                <strong className="block text-foreground">The Marketplace is unavailable right now</strong>
                {loaded.message}. Items you have installed keep working.
              </>
            ) : (
              <>Could not load the Marketplace: {loaded.message}</>
            )}{" "}
            <button
              type="button"
              className="underline"
              onClick={() => {
                setLoaded({ state: "loading" });
                setAttempt((n) => n + 1);
              }}
            >
              Retry
            </button>
          </>
        )}
      </p>
    );
  }

  const detail = detailKey ? market.find((e) => `${e.kind}/${e.id}` === detailKey) : undefined;
  if (detail) {
    return (
      <div className={className}>
        <Detail
          key={detailKey}
          entry={detail}
          busy={busy !== null}
          onBack={() => setDetailKey(null)}
          onInstall={() => void install(detail)}
          onRemove={() => void remove(detail)}
        />
      </div>
    );
  }

  const shown = filterEntries(market, { query, kinds });

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex h-9 min-w-48 flex-1 items-center gap-2 rounded-lg border border-input px-2.5 focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50">
          <Search className="size-3.5 text-muted-foreground" aria-hidden />
          <input
            aria-label="Search the Marketplace"
            placeholder="Search"
            value={query}
            autoFocus
            onChange={(e) => setQuery(e.target.value)}
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
        </div>
        <div role="tablist" aria-label="Kind" className="flex gap-1">
          {FILTERS.map((filter) => (
            <button
              key={filter.label}
              type="button"
              role="tab"
              aria-selected={sameKinds(kinds, filter.kinds)}
              onClick={() => setKinds(filter.kinds)}
              className={cn(
                "rounded-md px-2.5 py-1 text-xs font-medium text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50",
                sameKinds(kinds, filter.kinds) && "bg-muted text-foreground",
              )}
            >
              {filter.label}
            </button>
          ))}
        </div>
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          Updated {relativeTime(loaded.listing.fetched_at, now)}
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="Refresh the Marketplace"
            disabled={refreshing}
            onClick={() => void refresh()}
          >
            <RefreshCw className={cn("size-3.5", refreshing && "animate-spin")} aria-hidden />
          </Button>
        </span>
      </div>
      {loaded.listing.stale && (
        <p role="status" className="rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground">
          Showing a saved copy of the list. The Marketplace could not be reached to update it.
        </p>
      )}
      {shown.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">Nothing matches your search.</p>
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2">
          {shown.map((entry) => (
            <Card
              key={`${entry.kind}/${entry.id}`}
              entry={entry}
              busy={busy !== null}
              onInstall={() => void install(entry)}
              onRemove={() => void remove(entry)}
              onDetails={() => setDetailKey(`${entry.kind}/${entry.id}`)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
