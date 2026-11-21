"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import { MarketplaceView } from "./marketplace-view";
import { useMarketplace } from "./store";

// Mounted once in a layout; anything can open it with `openMarketplace`.
export function MarketplaceHost() {
  const options = useMarketplace((s) => s.options);
  const close = useMarketplace((s) => s.close);
  return (
    <Dialog open={options !== null} onOpenChange={(open) => !open && close()}>
      <DialogContent className="flex h-[calc(100dvh-2rem)] w-full flex-col sm:h-[80dvh] sm:max-h-[56rem] sm:w-[min(80vw,64rem)] sm:max-w-none">
        <DialogHeader className="shrink-0">
          <DialogTitle>Marketplace</DialogTitle>
          <DialogDescription>
            Add connections and templates to this workspace. Installed items appear in the pickers.
          </DialogDescription>
        </DialogHeader>
        {options && (
          <MarketplaceView kinds={options.kinds} onChanged={options.onChanged} className="min-h-0 flex-1" />
        )}
      </DialogContent>
    </Dialog>
  );
}
