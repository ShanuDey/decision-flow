"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import { save } from "./actions";
import { useLeave } from "./leave-store";
import { useEditor } from "./store";

export function LeaveDialog() {
  const pending = useLeave((s) => s.pending);
  const clear = useLeave((s) => s.clear);
  const name = useEditor((s) => s.name);
  const [saving, setSaving] = useState(false);

  async function saveAndLeave() {
    setSaving(true);
    const saved = await save();
    setSaving(false);
    if (!saved) return;
    const action = pending;
    clear();
    action?.();
  }

  function discard() {
    const action = pending;
    clear();
    action?.();
  }

  return (
    <Dialog open={pending !== null} onOpenChange={(open) => !open && clear()}>
      <DialogContent showCloseButton={false} className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Save changes before leaving?</DialogTitle>
          <DialogDescription>
            {name} has unsaved changes. If you leave without saving, they will be lost.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="outline"
            className="text-red-700 dark:text-red-400"
            onClick={discard}
            disabled={saving}
          >
            Discard
          </Button>
          <Button variant="outline" onClick={clear} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={saveAndLeave} disabled={saving}>
            {saving ? "Saving…" : "Save and leave"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
