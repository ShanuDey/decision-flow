import { Loader2 } from "lucide-react";

// Hidden for 3 s by CSS alone (see globals.css), so quick loads never show it.
export function WakingNotice() {
  return (
    <p
      role="status"
      aria-live="polite"
      className="reveal-after-3s flex items-start gap-2 text-sm text-muted-foreground"
    >
      <Loader2 className="mt-0.5 size-4 shrink-0 animate-spin" aria-hidden />
      <span>
        Starting the server. The free plan puts it to sleep when idle, so the first load can take
        up to a minute. This page opens by itself.
      </span>
    </p>
  );
}
