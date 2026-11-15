import Link from "next/link";

import { Badge } from "@/components/ui/badge";

// A soft-deleted flow has no page to open, so its name is plain text with a tag.
export function FlowCell({
  run,
}: {
  run: { flow_id: string; flow_name: string; flow_deleted: boolean };
}) {
  if (run.flow_deleted) {
    return (
      <span className="inline-flex items-center gap-2">
        {run.flow_name}
        <Badge variant="outline">Deleted flow</Badge>
      </span>
    );
  }
  return (
    <Link href={`/flows/${run.flow_id}`} className="font-medium text-foreground hover:underline">
      {run.flow_name}
    </Link>
  );
}
