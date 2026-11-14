import { CircleCheck, CircleX } from "lucide-react";

import type { RunSummary } from "@/lib/api/models";

export function RunStatus({ run }: { run: Pick<RunSummary, "status" | "error"> }) {
  return run.status === "succeeded" ? (
    <span className="inline-flex items-center gap-1.5 text-sm text-green-700 dark:text-green-400">
      <CircleCheck className="size-3.5" aria-hidden />
      Succeeded
    </span>
  ) : (
    <span
      title={run.error?.message}
      className="inline-flex items-center gap-1.5 text-sm text-red-700 dark:text-red-400"
    >
      <CircleX className="size-3.5" aria-hidden />
      Failed
    </span>
  );
}
