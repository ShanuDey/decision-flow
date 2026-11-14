import { WakingNotice } from "@/components/waking-notice";

function Bar({ className }: { className: string }) {
  return <div aria-hidden className={`animate-pulse rounded-md bg-muted ${className}`} />;
}

export default function Loading() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Bar className="h-8 w-40" />
      <Bar className="h-10 w-full max-w-xl" />
      <div className="flex flex-col gap-3 rounded-xl border p-4">
        <Bar className="h-5 w-full" />
        <Bar className="h-5 w-5/6" />
        <Bar className="h-5 w-2/3" />
      </div>
      <WakingNotice />
    </div>
  );
}
