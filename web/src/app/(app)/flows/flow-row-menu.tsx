"use client";

import { MoreHorizontal, Pencil, SquarePen, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { FlowDeleteDialog } from "@/components/flow-delete-dialog";
import { FlowRenameDialog } from "@/components/flow-rename-dialog";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function FlowRowMenu({ id, name }: { id: string; name: string }) {
  const router = useRouter();
  const [renaming, setRenaming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  // A new key remounts the rename dialog so it starts from the current name again.
  const [renameKey, setRenameKey] = useState(0);

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="ghost"
              size="icon"
              className="size-10"
              aria-label={`Actions for ${name}`}
            />
          }
        >
          <MoreHorizontal aria-hidden />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-40">
          <DropdownMenuItem render={<Link href={`/flows/${id}`} />}>
            <SquarePen aria-hidden /> Edit
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={() => {
              setRenameKey((k) => k + 1);
              setRenaming(true);
            }}
          >
            <Pencil aria-hidden /> Rename
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive" onClick={() => setDeleting(true)}>
            <Trash2 aria-hidden /> Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <FlowRenameDialog
        key={renameKey}
        flowId={id}
        currentName={name}
        open={renaming}
        onOpenChange={setRenaming}
        onRenamed={() => router.refresh()}
      />
      <FlowDeleteDialog
        flowId={id}
        name={name}
        open={deleting}
        onOpenChange={setDeleting}
        onDeleted={() => router.refresh()}
      />
    </>
  );
}
