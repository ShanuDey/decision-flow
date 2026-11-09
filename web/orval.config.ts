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
      baseUrl: { runtime: "process.env.NEXT_PUBLIC_API_URL" },
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
