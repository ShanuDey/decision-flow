import { describe, expect, it, vi } from "vitest";

import { retry } from "./retry";

const noSleep = async () => {};

describe("retry", () => {
  it("returns the first success without waiting", async () => {
    const sleep = vi.fn(noSleep);
    expect(await retry(async () => "ok", { sleep })).toBe("ok");
    expect(sleep).not.toHaveBeenCalled();
  });

  it("retries a transient failure with doubling delays", async () => {
    const delays: number[] = [];
    let calls = 0;
    const result = await retry(
      async () => {
        calls++;
        if (calls < 4) throw new Error("db waking up");
        return calls;
      },
      { delayMs: 100, sleep: async (ms) => void delays.push(ms) },
    );
    expect(result).toBe(4);
    expect(delays).toEqual([100, 200, 400]);
  });

  it("throws the last error once the attempts are used up", async () => {
    let calls = 0;
    await expect(
      retry(
        async () => {
          calls++;
          throw new Error(`failure ${calls}`);
        },
        { attempts: 3, sleep: noSleep },
      ),
    ).rejects.toThrow("failure 3");
    expect(calls).toBe(3);
  });

  it("reports each retry", async () => {
    const seen: number[] = [];
    await retry(
      async () => {
        if (seen.length < 2) throw new Error("x");
      },
      { sleep: noSleep, onRetry: (_error, attempt) => void seen.push(attempt) },
    );
    expect(seen).toEqual([1, 2]);
  });
});
