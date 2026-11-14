import { WakingNotice } from "@/components/waking-notice";

export default function Loading() {
  return (
    <main className="mx-auto flex max-w-lg flex-1 flex-col justify-center gap-4 p-8">
      <p className="text-sm font-medium">Opening the editor…</p>
      <WakingNotice />
    </main>
  );
}
