import { create } from "zustand";

export const DEFAULT_WIDTH = 320;
export const MIN_WIDTH = 280;
const MAX_FRACTION = 0.6;
const KEY = "decision-flow.editor-panel";

export const maxWidth = (viewport: number) =>
  Math.max(MIN_WIDTH, Math.floor(viewport * MAX_FRACTION));

export const clampWidth = (width: number, viewport: number) =>
  Math.round(Math.min(Math.max(width, MIN_WIDTH), maxWidth(viewport)));

interface Stored {
  width: number;
  collapsed: boolean;
}

type ReadStorage = Pick<Storage, "getItem">;
type WriteStorage = Pick<Storage, "setItem">;

// Storage can be missing or throw (private windows, blocked site data): fall back to defaults.
function browserStorage(): Storage | undefined {
  try {
    return typeof window === "undefined" ? undefined : window.localStorage;
  } catch {
    return undefined;
  }
}

export function loadStored(storage: ReadStorage | undefined = browserStorage()): Stored {
  const fallback = { width: DEFAULT_WIDTH, collapsed: false };
  try {
    const raw = storage?.getItem(KEY);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw) as Partial<Stored>;
    const width =
      typeof parsed.width === "number" && Number.isFinite(parsed.width)
        ? parsed.width
        : DEFAULT_WIDTH;
    return { width, collapsed: parsed.collapsed === true };
  } catch {
    return fallback;
  }
}

export function saveStored(value: Stored, storage: WriteStorage | undefined = browserStorage()) {
  try {
    storage?.setItem(KEY, JSON.stringify(value));
  } catch {
    // not persisting is fine
  }
}

// Asks the settings panel to focus a node's Name field once it has rendered (see configureNode).
export interface FocusRequest {
  select: boolean;
}

interface LayoutState extends Stored {
  // Replaced by a new object on every request, so asking twice for the same node still fires.
  focusRequest: FocusRequest | null;
  // `persist: false` while dragging; call `persist()` once when the drag ends.
  setWidth: (width: number, options?: { persist?: boolean }) => void;
  persist: () => void;
  reset: () => void;
  toggleCollapsed: () => void;
  expand: () => void;
  requestFocus: (request: FocusRequest) => void;
}

const viewport = () => (typeof window === "undefined" ? 1280 : window.innerWidth);

export const useLayout = create<LayoutState>()((set, get) => {
  const persist = () => {
    const { width, collapsed } = get();
    saveStored({ width, collapsed });
  };
  const update = (change: Partial<Stored>) => {
    set(change);
    persist();
  };
  return {
    ...loadStored(),
    focusRequest: null,
    setWidth: (width, { persist: save = true } = {}) => {
      const next = { width: clampWidth(width, viewport()) };
      if (save) update(next);
      else set(next);
    },
    persist,
    reset: () => update({ width: DEFAULT_WIDTH }),
    toggleCollapsed: () => update({ collapsed: !get().collapsed }),
    expand: () => update({ collapsed: false }),
    requestFocus: (focusRequest) => set({ focusRequest }),
  };
});
