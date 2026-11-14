import { defineConfig } from "orval";

const input = { target: "../api/openapi.json" };

export default defineConfig({
  client: {
    input,
    output: {
      client: "fetch",
      mode: "single",
      target: "src/lib/api/client.ts",
      schemas: "src/lib/api/models",
      override: { mutator: { path: "./src/lib/fetcher.ts", name: "apiFetch" } },
      clean: true,
    },
  },
  zod: {
    input,
    output: {
      client: "zod",
      mode: "single",
      target: "src/lib/api/zod.ts",
      override: { zod: { version: 4 } },
    },
  },
});
