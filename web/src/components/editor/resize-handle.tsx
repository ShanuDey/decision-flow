"use client";

import { useRef } from "react";

import { clampWidth, maxWidth, MIN_WIDTH, useLayout } from "./layout";

// Sits on the left edge of the settings panel (its parent must be `relative`).
export function ResizeHandle({ width, viewport }: { width: number; viewport: number }) {
  const setWidth = useLayout((s) => s.setWidth);
  const persist = useLayout((s) => s.persist);
  const reset = useLayout((s) => s.reset);
  const dragging = useRef(false);
  const max = maxWidth(viewport);

  function onPointerDown(event: React.PointerEvent<HTMLDivElement>) {
    dragging.current = true;
    event.currentTarget.setPointerCapture(event.pointerId);
    event.preventDefault();
  }

  function onPointerMove(event: React.PointerEvent<HTMLDivElement>) {
    if (!dragging.current) return;
    const panel = event.currentTarget.parentElement;
    // in memory only while dragging: one localStorage write on release, not one per move
    if (panel) setWidth(panel.getBoundingClientRect().right - event.clientX, { persist: false });
  }

  function endDrag() {
    if (!dragging.current) return;
    dragging.current = false;
    persist();
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const step = event.shiftKey ? 64 : 16;
    const next: Record<string, number> = {
      ArrowLeft: width + step, // the handle is on the left edge, so left = wider
      ArrowRight: width - step,
      Home: MIN_WIDTH,
      End: max,
    };
    if (!(event.key in next)) return;
    event.preventDefault();
    setWidth(clampWidth(next[event.key], viewport));
  }

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize settings panel"
      aria-valuemin={MIN_WIDTH}
      aria-valuemax={max}
      aria-valuenow={width}
      tabIndex={0}
      title="Drag to resize, double-click to reset"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      onDoubleClick={() => reset()}
      onKeyDown={onKeyDown}
      className="absolute inset-y-0 -left-1.5 z-10 hidden w-3 cursor-col-resize touch-none items-center justify-center outline-none lg:flex [&>span]:transition-colors hover:[&>span]:bg-ring focus-visible:[&>span]:bg-ring"
    >
      <span className="h-full w-0.5 rounded bg-transparent" aria-hidden />
    </div>
  );
}
