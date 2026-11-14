import { defineConfig, devices } from "@playwright/test";

import { AUTH_FILE, baseURL } from "./support/env";

export default defineConfig({
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL, trace: "retain-on-failure" },
  projects: [
    // Fails fast, with a fix, when the stack is down or its rate limits would cause 429s.
    { name: "preflight", testDir: "./preflight", testMatch: /.*\.preflight\.ts/ },
    {
      name: "setup",
      testDir: "./ui/setup",
      testMatch: /.*\.setup\.ts/,
      dependencies: ["preflight"],
    },
    {
      name: "ui",
      testDir: "./ui",
      testIgnore: "**/setup/**",
      dependencies: ["setup"],
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
        screenshot: "only-on-failure",
        storageState: AUTH_FILE,
      },
    },
    { name: "api", testDir: "./api", dependencies: ["preflight"] },
  ],
});
