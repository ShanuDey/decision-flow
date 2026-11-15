import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/auth/server", () => ({ getConfig: () => ({ apiUrl: "http://api.internal" }) }));

const BODY = JSON.stringify({ status: "degraded", checks: { postgres: "ok", mlflow: "fail" } });

describe("GET /status/ready", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("passes the API body and status through", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(BODY, { status: 503 })));
    const { GET } = await import("./route");
    const res = await GET();
    expect(res.status).toBe(503);
    expect(await res.text()).toBe(BODY);
    expect(fetch).toHaveBeenCalledWith("http://api.internal/ready", expect.anything());
  });

  it("serves repeat calls from cache until it expires", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => new Response(BODY, { status: 503 })));
    const { GET, CACHE_MS } = await import("./route");
    await GET();
    await GET();
    expect(fetch).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(CACHE_MS);
    await GET();
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("answers 502 when the API is unreachable and does not cache it", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    const { GET } = await import("./route");
    expect((await GET()).status).toBe(502);
    expect((await GET()).status).toBe(502);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("answers 502 for an unexpected upstream status", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("no", { status: 429 })));
    const { GET } = await import("./route");
    expect((await GET()).status).toBe(502);
  });
});
