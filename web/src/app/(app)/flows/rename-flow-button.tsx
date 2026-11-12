"use client";

import { Pencil } from "lucide-react";
import { useRouter } from "next/navigation";

import { FlowRenameDialog } from "@/components/flow-rename-dialog";
import { Button } from "@/components/ui/button";

export function RenameFlowButton({ id, name }: { id: string; name: string }) {
  const router = useRouter();
  return (
    <FlowRenameDialog
      flowId={id}
      currentName={name}
      onRenamed={() => router.refresh()}
      trigger={
        <Button variant="ghost" size="icon" className="size-10" aria-label={`Rename ${name}`}>
          <Pencil aria-hidden />
        </Button>
      }
    />
  );
}
