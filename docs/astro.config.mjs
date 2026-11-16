import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";
import mermaid from "astro-mermaid";

import { PROD_APP_URL } from "./src/lib/prod-app-url.mjs";

// Two builds ship: /docs (behind the app's rewrite) and /decision-flow (the Pages root).
const base = `/${(process.env.DOCS_BASE ?? "docs").replace(/^\/+/, "")}`;
// The copy behind the app's rewrite duplicates the Pages root, so keep it out of search.
const head = process.env.DOCS_NOINDEX ? [{ tag: "meta", attrs: { name: "robots", content: "noindex" } }] : [];

export default defineConfig({
  site: process.env.DOCS_SITE ?? PROD_APP_URL,
  base,
  outDir: process.env.DOCS_OUT ?? "dist",
  trailingSlash: "never",
  build: { format: "file" },
  devToolbar: { enabled: false },
  server: { port: 4321 },
  vite: { server: { strictPort: true } },
  integrations: [
    mermaid(),
    starlight({
      title: "Decision Flow",
      head,
      logo: { src: "./src/assets/logo.svg" },
      components: {
        SocialIcons: "./src/components/SocialIcons.astro",
        Search: "./src/components/Search.astro",
      },
      social: [
        {
          icon: "github",
          label: "GitHub",
          href: "https://github.com/ShanuDey/decision-flow",
        },
      ],
      sidebar: [
        {
          label: "Start here",
          items: ["overview", "getting-started", "agent-guide"],
        },
        {
          label: "Concepts",
          items: [
            "concepts/variables",
            "concepts/templates",
            "concepts/expressions",
            "flow-templates",
          ],
        },
        {
          label: "Nodes",
          items: [
            "nodes/start",
            "nodes/assign",
            "nodes/condition",
            "nodes/http-request",
            "nodes/end",
          ],
        },
        { label: "Runs", items: ["traces"] },
        {
          label: "Operations",
          items: [
            "auth",
            "mcp",
            "secrets",
            "configuration",
            "limits",
            "data-deletion",
            "retention",
          ],
        },
        { label: "API reference", link: "/api" },
      ],
    }),
  ],
});
