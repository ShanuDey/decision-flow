import type { Metadata } from "next";

import { MarketplaceView } from "@/components/marketplace/marketplace-view";

export const metadata: Metadata = { title: "Marketplace · Decision Flow" };

export default function MarketplacePage() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Marketplace</h1>
        <p className="max-w-xl text-sm text-muted-foreground">
          Add connections and templates to this workspace. Installed items appear in the Add connection and
          template pickers.
        </p>
      </div>
      <MarketplaceView kinds={null} />
    </div>
  );
}
