"use client";

import { useState } from "react";

import { openMarketplace } from "@/components/marketplace/store";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { SelectField } from "@/components/ui/select-field";
import type { ConnectionOption } from "@/lib/connections";
import type { ConnectionNeed } from "@/lib/graph/transfer";

export function ImportConnectionsDialog({
  needs,
  options,
  typeNames,
  busy,
  onConfirm,
  onCancel,
}: {
  needs: ConnectionNeed[];
  options: ConnectionOption[];
  typeNames: Record<string, string>;
  busy: boolean;
  onConfirm: (choices: Record<string, string>) => void;
  onCancel: () => void;
}) {
  const [choices, setChoices] = useState<Record<string, string>>(() =>
    Object.fromEntries(needs.map((n) => [n.fileId, n.suggestion ?? ""])),
  );

  return (
    <Dialog open onOpenChange={(open) => !open && !busy && onCancel()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Match connections</DialogTitle>
          <DialogDescription>
            This flow used connections from another workspace. Choose one of yours for each, or leave it empty and
            pick later. Credentials are never exported.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          {needs.map((need) => {
            const matching = need.type ? options.filter((o) => o.typeId === need.type) : options;
            const id = `import-connection-${need.fileId}`;
            const typeName = typeNames[need.type] ?? need.type;
            return (
              <div key={need.fileId} className="flex flex-col gap-1.5">
                <Label htmlFor={id}>
                  {need.name}
                  {typeName && <span className="font-normal text-muted-foreground"> ({typeName})</span>}
                </Label>
                <SelectField
                  id={id}
                  value={choices[need.fileId] ?? ""}
                  onValueChange={(next) => setChoices((current) => ({ ...current, [need.fileId]: next }))}
                  options={[
                    { value: "", label: "Leave empty" },
                    ...matching.map((o) => ({ value: o.id, label: `${o.name} (${o.typeName})` })),
                  ]}
                />
                <p className="text-xs text-muted-foreground">
                  Used by {need.nodes} request {need.nodes === 1 ? "node" : "nodes"}.
                  {matching.length === 0 && (
                    <>
                      {" "}
                      You have no {typeName || "matching"} connection. Add one under Connections, or{" "}
                      <button
                        type="button"
                        className="underline underline-offset-2 hover:text-foreground"
                        onClick={() => openMarketplace({ kinds: ["connection-type"] })}
                      >
                        browse the Marketplace
                      </button>{" "}
                      for the type.
                    </>
                  )}
                </p>
              </div>
            );
          })}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" disabled={busy} onClick={onCancel}>
            Cancel
          </Button>
          <Button type="button" disabled={busy} onClick={() => onConfirm(choices)}>
            {busy ? "Importing…" : "Import flow"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
