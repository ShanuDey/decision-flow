"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatKeyDate, keyStatus, MAX_KEYS } from "@/lib/auth/key-request";
import type { Action } from "@/lib/auth/scopes";

import { CreateKeyDialog } from "./create-key-dialog";
import { RevokeKeyDialog } from "./revoke-key-dialog";

export interface KeyRow {
  id: string;
  name: string;
  start: string;
  actions: Action[];
  expiresAt: string | null;
  lastUsedAt: string | null;
  createdAt: string;
}

export function ApiKeysPanel({ rows }: { rows: KeyRow[] }) {
  return (
    <section className="flex flex-col gap-4" aria-labelledby="api-keys-heading">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex max-w-xl flex-col gap-1">
          <h2 id="api-keys-heading" className="text-lg font-medium">
            API keys
          </h2>
          <p className="text-sm text-muted-foreground">
            Keys let scripts and tools use your flows without signing in. A key acts as you, limited to
            the scopes you pick.{" "}
            <Link href="/docs/api" className="underline underline-offset-2 hover:text-foreground">
              API reference
            </Link>
          </p>
        </div>
        <CreateKeyDialog atLimit={rows.length >= MAX_KEYS} />
      </div>

      {rows.length === 0 ? (
        <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
          No keys yet. Create one to call your flows from code.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Key</TableHead>
                <TableHead>Scopes</TableHead>
                <TableHead>Last used</TableHead>
                <TableHead>Expires</TableHead>
                <TableHead className="w-0">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="font-medium">{row.name}</TableCell>
                  <TableCell className="font-mono text-xs">{row.start}…</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {row.actions.map((action) => (
                        <Badge key={action} variant="secondary" className="capitalize">
                          {action}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {row.lastUsedAt ? formatKeyDate(row.lastUsedAt) : "Never"}
                  </TableCell>
                  <TableCell>
                    {keyStatus(row.expiresAt) === "expired" ? (
                      <Badge variant="destructive">Expired</Badge>
                    ) : row.expiresAt ? (
                      formatKeyDate(row.expiresAt)
                    ) : (
                      <span className="text-muted-foreground">Never</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <RevokeKeyDialog keyId={row.id} name={row.name} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  );
}
