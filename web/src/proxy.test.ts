import { describe, expect, it } from "vitest";

import { config } from "./proxy";

const guarded = (path: string) => new RegExp(`^${config.matcher[0]}$`).test(path);

describe("proxy matcher", () => {
  it("leaves the landing page and auth routes public", () => {
    for (const path of ["/", "/login", "/api/auth/get-session", "/backend/flows", "/warm", "/@id/x", "/@vite/client", "/@astro/x", "/src/pages/api.astro", "/node_modules/x.css"]) {
      expect(guarded(path), path).toBe(false);
    }
  });

  it("guards app pages", () => {
    for (const path of ["/overview", "/flows", "/flows/abc", "/settings/account", "/@fs/x.svg"]) {
      expect(guarded(path), path).toBe(true);
    }
  });
});
