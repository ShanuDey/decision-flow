import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";

import { PROD_APP_URL } from "./src/lib/prod-app-url.mjs";

export default defineConfig({
  site: PROD_APP_URL,
  base: "/docs",
  trailingSlash: "never",
  build: { format: "file" },
  devToolbar: { enabled: false },
  integrations: [
    starlight({
      title: "Decision Flow",
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
          items: ["nodes/start", "nodes/assign", "nodes/condition", "nodes/end"],
        },
        { label: "Runs", items: ["traces"] },
        {
          label: "Operations",
          items: [
            "auth",
            "mcp",
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
