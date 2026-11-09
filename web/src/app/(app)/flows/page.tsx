import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, CircleX } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { listFlows } from "@/lib/api/client";
import { call } from "@/lib/call";
import { ListFlowsSort } from "@/lib/api/models";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

import { NewFlowButton } from "./new-flow-button";

export const metadata: Metadata = { title: "Flows · Decision Flow" };

const PAGE_SIZE = 25;
const SORTABLE = ["name", "updated_at", "created_at"] as const;
type SortKey = (typeof SORTABLE)[number];

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function parseSort(raw: string | undefined): { key: SortKey; desc: boolean } {
  const desc = raw?.startsWith("-") ?? true;
  const key = raw?.replace(/^-/, "") as SortKey;
  return SORTABLE.includes(key) ? { key, desc } : { key: "updated_at", desc: true };
}

function href(q: string | undefined, sort: string, page: number): string {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  params.set("sort", sort);
  if (page > 1) params.set("page", String(page));
  return `/flows?${params}`;
}

export default async function FlowsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const q = first(sp.q)?.trim() || undefined;
  const { key, desc } = parseSort(first(sp.sort));
  const sort = `${desc ? "-" : ""}${key}`;
  const page = Math.max(1, Number.parseInt(first(sp.page) ?? "1", 10) || 1);

  const result = await call(
    listFlows(
      { q, sort: sort as ListFlowsSort, page, page_size: PAGE_SIZE },
      { cache: "no-store" },
    ),
  );

  const header = (label: string, column: SortKey) => {
    const active = key === column;
    const next = active && !desc ? `-${column}` : column;
    return (
      <Link
        href={href(q, next, 1)}
        className="inline-flex items-center gap-1 hover:underline"
        aria-label={`Sort by ${label}`}
      >
        {label}
        {active && (desc ? <ArrowDown className="size-3.5" /> : <ArrowUp className="size-3.5" />)}
      </Link>
    );
  };

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Flows</h1>
        <NewFlowButton />
      </div>

      <form action="/flows" className="flex gap-2" role="search">
        <input type="hidden" name="sort" value={sort} />
        <label htmlFor="q" className="sr-only">
          Search flows
        </label>
        <Input id="q" name="q" defaultValue={q} placeholder="Search by name" className="h-10 max-w-sm" />
        <button type="submit" className={cn(buttonVariants({ variant: "outline" }), "h-10")}>
          Search
        </button>
        {q && (
          <Link href={href(undefined, sort, 1)} className={cn(buttonVariants({ variant: "ghost" }), "h-10")}>
            Clear
          </Link>
        )}
      </form>

      {!result.ok ? (
        <p role="alert" className="flex items-center gap-2 rounded-xl border p-4 text-sm">
          <CircleX className="size-4 text-red-600 dark:text-red-400" aria-hidden />
          Could not load flows: {result.error.message}
        </p>
      ) : result.data.total === 0 ? (
        <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
          {q ? `No flows match “${q}”.` : "No flows yet. Create your first flow to get started."}
        </div>
      ) : (
        <>
          <div className="rounded-xl border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{header("Name", "name")}</TableHead>
                  <TableHead>Draft</TableHead>
                  <TableHead>{header("Updated", "updated_at")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {result.data.items.map((flow) => (
                  <TableRow key={flow.id}>
                    <TableCell className="font-medium">
                      <Link href={`/flows/${flow.id}`} className="hover:underline">
                        {flow.name}
                      </Link>
                    </TableCell>
                    <TableCell className="text-muted-foreground">v{flow.draft_version}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDateTime(flow.updated_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <Pager q={q} sort={sort} page={page} total={result.data.total} />
        </>
      )}
    </div>
  );
}

function Pager({ q, sort, page, total }: { q?: string; sort: string; page: number; total: number }) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const link = cn(buttonVariants({ variant: "outline" }), "h-10");
  const disabled = cn(link, "pointer-events-none opacity-50");
  return (
    <div className="flex items-center justify-between text-sm text-muted-foreground">
      <span>
        {total} flow{total === 1 ? "" : "s"} · page {Math.min(page, pages)} of {pages}
      </span>
      <div className="flex gap-2">
        {page > 1 ? (
          <Link href={href(q, sort, page - 1)} className={link}>
            <ChevronLeft aria-hidden /> Previous
          </Link>
        ) : (
          <span aria-disabled="true" className={disabled}>
            <ChevronLeft aria-hidden /> Previous
          </span>
        )}
        {page < pages ? (
          <Link href={href(q, sort, page + 1)} className={link}>
            Next <ChevronRight aria-hidden />
          </Link>
        ) : (
          <span aria-disabled="true" className={disabled}>
            Next <ChevronRight aria-hidden />
          </span>
        )}
      </div>
    </div>
  );
}
