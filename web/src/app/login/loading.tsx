import { WakingNotice } from "@/components/waking-notice";

import { AuthShell } from "../auth-shell";

function Bar({ className }: { className: string }) {
  return <div aria-hidden className={`animate-pulse rounded-md bg-muted ${className}`} />;
}

export default function Loading() {
  return (
    <AuthShell title="Sign in">
      <Bar className="h-9 w-full" />
      <Bar className="h-9 w-full" />
      <Bar className="h-9 w-full" />
      <WakingNotice />
    </AuthShell>
  );
}
