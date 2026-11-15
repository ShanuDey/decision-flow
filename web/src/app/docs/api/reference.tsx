"use client";

import "@scalar/api-reference-react/style.css";

import { ApiReferenceReact } from "@scalar/api-reference-react";
import { useTheme } from "next-themes";

export function Reference() {
  const { resolvedTheme } = useTheme();
  return (
    <ApiReferenceReact
      configuration={{
        url: "/docs/api/openapi.json",
        darkMode: resolvedTheme === "dark",
        hideDarkModeToggle: true,
        hideClientButton: true,
        showDeveloperTools: "never",
        agent: { disabled: true },
        mcp: { disabled: true },
        telemetry: false,
        layout: "modern",
      }}
    />
  );
}
