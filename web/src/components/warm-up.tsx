"use client";

import { useEffect } from "react";

export function WarmUp() {
  useEffect(() => {
    void fetch("/warm", { cache: "no-store" }).catch(() => undefined);
  }, []);
  return null;
}
