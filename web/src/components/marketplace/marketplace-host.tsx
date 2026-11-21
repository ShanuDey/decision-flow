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
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Marketplace</DialogTitle>
          <DialogDescription>
            Add connections and templates to this workspace. Installed items appear in the pickers.
          </DialogDescription>
        </DialogHeader>
        {options && (
          <MarketplaceView
            kinds={options.kinds}
            onChanged={options.onChanged}
            className="max-h-[min(520px,65vh)] overflow-y-auto"
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
