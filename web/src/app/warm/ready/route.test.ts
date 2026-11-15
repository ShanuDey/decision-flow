import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/auth/server", () => ({ getConfig: () => ({ apiUrl: "http://api.internal" }) }));

describe("GET /warm/ready", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("answers 204 once the API health check passes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("ok")));
    const { GET } = await import("./route");
    expect((await GET()).status).toBe(204);
    expect(fetch).toHaveBeenCalledWith("http://api.internal/health", expect.anything());
  });

  it("answers 503 while the API is unhealthy", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("no", { status: 502 })));
    const { GET } = await import("./route");
    expect((await GET()).status).toBe(503);
  });

  it("answers 503 when the API is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    const { GET } = await import("./route");
    expect((await GET()).status).toBe(503);
  });
});
