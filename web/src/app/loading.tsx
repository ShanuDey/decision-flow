import { Loader2 } from "lucide-react";

import { WakingNotice } from "@/components/waking-notice";

// Covers layouts that await the session, which nested loading.tsx files cannot.
export default function Loading() {
  return (
    <div className="flex min-h-screen flex-1 flex-col items-center justify-center gap-4 px-6">
      <Loader2 className="size-6 animate-spin text-muted-foreground" aria-label="Loading" />
      <div className="max-w-md">
        <WakingNotice />
      </div>
    </div>
  );
}
