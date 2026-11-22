"use client";

import { ComposerPrimitive, useAuiState, WebSpeechDictationAdapter } from "@assistant-ui/react";
import { Mic, Square } from "lucide-react";
import { useEffect, useSyncExternalStore } from "react";
import { toast } from "sonner";

import { dictationProblem } from "@/lib/dictation";

const BUTTON =
  "flex size-8 items-center justify-center rounded-full outline-none focus-visible:ring-3 focus-visible:ring-ring/50";

export function DictationPreview() {
  const dictating = useAuiState((s) => s.composer.dictation != null);
  if (!dictating) return null;
  return (
    <span className="flex min-w-0 flex-1 items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
      <Mic className="size-4 shrink-0 animate-pulse text-red-500" aria-hidden />
      <span className="truncate">
        <ComposerPrimitive.DictationTranscript />
      </span>
    </span>
  );
}

// The library only logs a failed session, so this toasts it.
export function DictationButton({ disabled }: { disabled: boolean }) {
  const supported = useSyncExternalStore(
    () => () => {},
    () => WebSpeechDictationAdapter.isSupported(),
    () => false,
  );
  const dictating = useAuiState((s) => s.composer.dictation != null);
  const end = useAuiState((s) => s.composer.lastDictationEnd);

  useEffect(() => {
    if (end?.reason !== "error") return;
    const message = dictationProblem(end.error?.code);
    if (message) toast.error(message, { id: "dictation" });
  }, [end]);

  if (dictating) {
    return (
      <ComposerPrimitive.StopDictation aria-label="Stop voice input" className={`${BUTTON} border border-red-500/50 text-red-500`}>
        <Square className="size-3.5 fill-current" aria-hidden />
      </ComposerPrimitive.StopDictation>
    );
  }
  if (!supported) return null;
  return (
    <ComposerPrimitive.Dictate
      aria-label="Start voice input"
      title="Speak instead of typing"
      disabled={disabled}
      className={`${BUTTON} text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-30`}
    >
      <Mic className="size-4" aria-hidden />
    </ComposerPrimitive.Dictate>
  );
}
