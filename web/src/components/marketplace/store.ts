import { create } from "zustand";

import type { Kind } from "@/lib/marketplace";

export interface MarketplaceOptions {
  // Limits what the modal lists; null shows everything.
  kinds: Kind[] | null;
  // Called after something is installed or removed, so the caller can refresh its own list.
  onChanged?: () => void;
}

interface MarketplaceState {
  options: MarketplaceOptions | null;
  open: (options: MarketplaceOptions) => void;
  close: () => void;
}

export const useMarketplace = create<MarketplaceState>()((set) => ({
  options: null,
  open: (options) => set({ options }),
  close: () => set({ options: null }),
}));

export const openMarketplace = (options: MarketplaceOptions) => useMarketplace.getState().open(options);
