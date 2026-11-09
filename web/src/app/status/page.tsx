import type { Metadata } from "next";

import { StatusCard } from "./status-card";

export const metadata: Metadata = { title: "Status · Decision Flow" };

export default function StatusPage() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-3xl font-semibold tracking-tight">Decision Flow</h1>
      <StatusCard />
    </main>
  );
}
