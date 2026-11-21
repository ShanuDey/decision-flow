import { defineConfig, devices } from "@playwright/test";

// The docs site is static, so these tests need neither the stack nor a sign-in.
export default defineConfig({
  testDir: "./docs",
  retries: 0,
  reporter: [["list"]],
  use: { baseURL: "http://localhost:4321", ...devices["Desktop Chrome"], trace: "retain-on-failure" },
  webServer: {
    command: "pnpm --dir ../docs dev",
    url: "http://localhost:4321/docs",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
