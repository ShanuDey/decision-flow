"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDateTime } from "@/lib/format";

import { DeleteSecretDialog } from "./delete-secret-dialog";
import { SecretDialog } from "./secret-dialog";

export interface SecretRow {
  name: string;
  createdAt: string;
  updatedAt: string;
}

export function SecretsPanel({ rows }: { rows: SecretRow[] }) {
  const names = rows.map((row) => row.name);
  return (
    <section className="flex flex-col gap-4" aria-labelledby="secrets-heading">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex max-w-xl flex-col gap-1">
          <h2 id="secrets-heading" className="text-lg font-medium">
            Secrets
          </h2>
          <p className="text-sm text-muted-foreground">
            Store values such as API tokens by name. A node that supports secrets can read one as{" "}
            <code className="font-mono text-xs">{"{{ secrets.NAME }}"}</code>. A saved value is
            encrypted and never shown again; to change it, replace it.
          </p>
        </div>
        <SecretDialog mode="add" existing={names} />
      </div>

      {rows.length === 0 ? (
        <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
          No secrets yet. Add one to use it in a flow.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Value</TableHead>
                <TableHead>Updated</TableHead>
                <TableHead className="w-0">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.name}>
                  <TableCell className="font-mono text-xs font-medium">{row.name}</TableCell>
                  <TableCell className="text-muted-foreground" aria-label="Hidden">
                    ••••••••
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDateTime(row.updatedAt)}
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-right">
                    <SecretDialog mode="replace" name={row.name} />
                    <DeleteSecretDialog name={row.name} />
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
