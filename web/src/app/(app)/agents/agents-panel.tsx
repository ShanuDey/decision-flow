"use client";

import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { AgentSummary } from "@/lib/api/models";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

import { DeleteAgentDialog } from "./delete-agent-dialog";
import { NewAgentDialog } from "./new-agent-dialog";

export function AgentsPanel({
  agents,
  connectionNames,
}: {
  agents: AgentSummary[];
  connectionNames: Record<string, string>;
}) {
  return (
    <section className="flex flex-col gap-4" aria-labelledby="agents-intro">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <p id="agents-intro" className="max-w-xl text-sm text-muted-foreground">
          An agent is a chat you can talk to. It uses a model from one of your connections and can run your published
          flows as tools to look things up or take actions. Each person keeps their own conversations.
        </p>
        <NewAgentDialog existing={agents.map((a) => a.name)} />
      </div>

      {agents.length === 0 ? (
        <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
          No agents yet. Create one, then give it a connection and some flows.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Connection</TableHead>
                <TableHead>Tools</TableHead>
                <TableHead>Updated</TableHead>
                <TableHead className="w-0">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {agents.map((agent) => (
                <TableRow key={agent.id}>
                  <TableCell className="font-medium">
                    <Link href={`/agents/${agent.id}`} className="underline-offset-2 hover:underline">
                      {agent.name}
                    </Link>
                    {agent.description && (
                      <span className="block max-w-sm truncate text-xs font-normal text-muted-foreground">
                        {agent.description}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {agent.connection_id ? (connectionNames[agent.connection_id] ?? "Missing") : "Not set"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{agent.tools?.length ?? 0}</TableCell>
                  <TableCell className="text-muted-foreground">{formatDateTime(agent.updated_at)}</TableCell>
                  <TableCell className="whitespace-nowrap text-right">
                    <Link
                      href={`/agents/${agent.id}`}
                      className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}
                    >
                      Open
                    </Link>
                    <DeleteAgentDialog id={agent.id} name={agent.name} />
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
