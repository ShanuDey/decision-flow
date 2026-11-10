"use client";

import dynamic from "next/dynamic";

// The canvas needs the browser, so it is never rendered on the server.
export const EditorLoader = dynamic(() => import("@/components/editor/editor"), {
  ssr: false,
  loading: () => <p className="p-8 text-sm text-muted-foreground">Loading editor…</p>,
});
