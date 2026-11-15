import type { Metadata } from "next";

import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

import { Reference } from "./reference";

export const metadata: Metadata = {
  title: "API reference | Decision Flow",
  description: "Run and manage Decision Flow flows over HTTP with an API key.",
};

export default function ApiDocsPage() {
  return (
    <div
      className="flex min-h-screen flex-1 flex-col"
      style={{ "--scalar-custom-header-height": "3.5625rem" } as React.CSSProperties}
    >
      <div className="sticky top-0 z-50 bg-background">
        <SiteHeader />
      </div>
      <main className="flex-1">
        <Reference />
      </main>
      <SiteFooter />
    </div>
  );
}
