import { defineConfig } from "orval";

const input = { target: "../api/openapi.json" };
// The root tsconfig allows .ts import extensions, which would leak into the generated client.
const tsconfig = { compilerOptions: {} };

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
      tsconfig,
    },
  },
  zod: {
    input,
    output: {
      client: "zod",
      mode: "single",
      target: "src/lib/api/zod.ts",
      override: { zod: { version: 4 } },
      tsconfig,
    },
  },
});
