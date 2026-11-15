import type { Metadata } from "next";

import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

import { StatusCard } from "./status-card";

export const metadata: Metadata = { title: "Status · Decision Flow" };

export default function StatusPage() {
  return (
    <div className="flex min-h-screen flex-1 flex-col">
      <SiteHeader />
      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col items-center px-5 py-12 md:px-8 md:py-16">
        <StatusCard />
      </main>
      <SiteFooter />
    </div>
  );
}
