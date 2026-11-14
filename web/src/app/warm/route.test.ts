import { beforeEach, describe, expect, it, vi } from "vitest";

const pending: Promise<unknown>[] = [];
vi.mock("next/server", () => ({ after: (task: () => Promise<unknown>) => pending.push(task()) }));
vi.mock("@/lib/auth/server", () => ({ getConfig: () => ({ apiUrl: "http://api.internal" }) }));

describe("GET /warm", () => {
  beforeEach(() => {
    pending.length = 0;
    vi.resetModules();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("ok")));
  });

  it("answers at once and pings the API only once per gap", async () => {
    const { GET } = await import("./route");
    expect(GET().status).toBe(204);
    expect(GET().status).toBe(204);
    await Promise.all(pending);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith("http://api.internal/health", expect.anything());
  });

  it("does not fail when the API is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    const { GET } = await import("./route");
    expect(GET().status).toBe(204);
    await expect(Promise.all(pending)).resolves.toBeDefined();
  });
});
