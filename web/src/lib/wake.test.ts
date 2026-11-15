import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const pending = vi.hoisted(() => [] as Promise<unknown>[]);
const state = vi.hoisted(() => ({ scheduleFails: false }));
vi.mock("next/server", () => ({
  after: (work: () => Promise<unknown>) => {
    if (state.scheduleFails) throw new Error("outside a request");
    pending.push(work());
  },
}));
vi.mock("./auth/server", () => ({ getConfig: () => ({ apiUrl: "http://api.test" }) }));

import { MIN_GAP_MS, wakeApi } from "./wake";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValue(new Response(null, { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  pending.length = 0;
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// The gap is module state, so each test starts later than the last one ended.
let clock = 1_000_000;
const later = (ms: number) => (clock += ms);

describe("wakeApi", () => {
  it("pings the API's health in the background", async () => {
    wakeApi(later(2 * MIN_GAP_MS));
    await Promise.all(pending);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("http://api.test/health");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ cache: "no-store" });
  });

  it("pings at most once per gap", async () => {
    const start = later(MIN_GAP_MS);
    wakeApi(start);
    wakeApi(start + 1_000);
    wakeApi(start + MIN_GAP_MS - 1);
    await Promise.all(pending);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    wakeApi(start + MIN_GAP_MS);
    await Promise.all(pending);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not start the gap until the ping is scheduled", () => {
    const start = later(2 * MIN_GAP_MS);
    state.scheduleFails = true;
    expect(() => wakeApi(start)).toThrow();
    state.scheduleFails = false;
    wakeApi(start + 1);
    expect(pending).toHaveLength(1);
  });

  it("never throws when the API is unreachable", async () => {
    fetchMock.mockRejectedValue(new Error("connect ECONNREFUSED"));
    wakeApi(later(2 * MIN_GAP_MS));
    await expect(Promise.all(pending)).resolves.toBeDefined();
  });
});
