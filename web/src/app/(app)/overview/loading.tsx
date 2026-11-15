import { WakingNotice } from "@/components/waking-notice";

function Bar({ className }: { className: string }) {
  return <div aria-hidden className={`animate-pulse rounded-md bg-muted ${className}`} />;
}

export default function Loading() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Bar className="h-8 w-56" />
        <Bar className="h-4 w-72" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Bar className="h-24 w-full" />
        <Bar className="h-24 w-full" />
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Bar className="h-56 w-full" />
        <Bar className="h-56 w-full" />
      </div>
      <WakingNotice />
    </div>
  );
}
