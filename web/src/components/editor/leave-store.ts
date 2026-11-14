import { useRouter } from "next/navigation";
import { create } from "zustand";

import { useEditor } from "./store";

interface LeaveState {
  pending: (() => void) | null;
  ask: (action: () => void) => void;
  clear: () => void;
}

export const useLeave = create<LeaveState>()((set) => ({
  pending: null,
  ask: (action) => set({ pending: action }),
  clear: () => set({ pending: null }),
}));

// Runs `action` straight away, or after the user decides what to do with unsaved changes.
export function guardedLeave(action: () => void): void {
  if (useEditor.getState().dirty) useLeave.getState().ask(action);
  else action();
}

export function useGuardedNavigate(): (href: string) => void {
  const router = useRouter();
  return (href) => guardedLeave(() => router.push(href));
}
