import { WakingNotice } from "@/components/waking-notice";

function Bar({ className }: { className: string }) {
  return <div aria-hidden className={`animate-pulse rounded-md bg-muted ${className}`} />;
}

export default function Loading() {
  return (
    <div className="flex flex-col gap-4">
      <Bar className="h-8 w-48" />
      <div className="grid gap-4 lg:grid-cols-[380px_minmax(0,1fr)]">
        <Bar className="h-64 w-full" />
        <Bar className="h-64 w-full" />
      </div>
      <WakingNotice />
    </div>
  );
}
