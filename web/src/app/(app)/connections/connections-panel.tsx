"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { testConnection } from "@/lib/api/client";
import type { ConnectionSummary, ConnectionTypeInfo } from "@/lib/api/models";
import { errorToast } from "@/lib/api-error";
import { call } from "@/lib/call";
import { hostsLabel, type Prefill } from "@/lib/connections";
import { formatDateTime } from "@/lib/format";

import { ConnectionDialog } from "./connection-dialog";
import { DeleteConnectionDialog } from "./delete-connection-dialog";

function TestButton({ id, name }: { id: string; name: string }) {
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    const result = await call(testConnection(id));
    setBusy(false);
    if (!result.ok) {
      errorToast("Could not test the connection", result.error);
      return;
    }
    if (result.data.ok) toast.success(`${name}: ${result.data.message}`);
    else toast.error(`${name}: ${result.data.message}`);
  }

  return (
    <Button variant="ghost" size="sm" disabled={busy} onClick={() => void run()}>
      {busy ? "Testing…" : "Test"}
    </Button>
  );
}

export function ConnectionsPanel({
  connections,
  types,
  prefill,
}: {
  connections: ConnectionSummary[];
  types: ConnectionTypeInfo[];
  prefill: Prefill | null;
}) {
  const router = useRouter();
  const byId = new Map(types.map((t) => [t.id, t]));

  return (
    <section className="flex flex-col gap-4" aria-labelledby="connections-intro">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <p id="connections-intro" className="max-w-xl text-sm text-muted-foreground">
          A connection holds the credentials for a service. Pick it in an HTTP Request node and its
          credentials are added to the request, only for the hosts it allows. A saved credential is
          encrypted and never shown again; to change it, edit the connection.
        </p>
        <ConnectionDialog
          mode="add"
          types={types}
          existing={connections.map((c) => c.name)}
          initial={prefill ?? undefined}
          onSaved={() => router.refresh()}
        />
      </div>

      {connections.length === 0 ? (
        <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
          No connections yet. Add one to use it in a flow.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Allowed hosts</TableHead>
                <TableHead>Updated</TableHead>
                <TableHead className="w-0">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {connections.map((connection) => {
                const type = byId.get(connection.type);
                return (
                  <TableRow key={connection.id}>
                    <TableCell className="font-medium">{connection.name}</TableCell>
                    <TableCell className="text-muted-foreground">{type?.name ?? connection.type}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {hostsLabel(connection, type)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDateTime(connection.updated_at)}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-right">
                      {type?.testable && <TestButton id={connection.id} name={connection.name} />}
                      {type && (
                        <ConnectionDialog
                          key={connection.updated_at}
                          mode="edit"
                          type={type}
                          connection={connection}
                          onSaved={() => router.refresh()}
                        />
                      )}
                      <DeleteConnectionDialog id={connection.id} name={connection.name} />
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  );
}
