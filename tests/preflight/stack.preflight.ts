import { expect, test } from "@playwright/test";

import { backend, signedInApi } from "../support/api";
import { baseURL, testName } from "../support/env";

// A limit that is off sends no RateLimit-Limit header. Anything below this is a real limit.
const RELAXED = 1000;

const hint = `Set these in the repo-root .env, then restart the API (make start):
  RATE_LIMIT_IP_PER_MINUTE=0
  RATE_LIMIT_USER_WRITES_PER_MINUTE=0
  RATE_LIMIT_USER_RUNS_PER_MINUTE=0`;

function limitOf(headers: Record<string, string>): number {
  return Number(headers["ratelimit-limit"] ?? 0);
}

test("the stack is up and its rate limits allow a full test run", async ({ request }) => {
  const health = await request.get("/api/auth/ok").catch(() => null);
  expect(
    health?.status(),
    `The web server at ${baseURL} is not healthy. Start it with 'make start' (or restart 'make web').`,
  ).toBe(200);

  const api = await signedInApi();
  try {
    const list = await api.get(backend("/flows"));
    expect(list.status(), "listing flows through the web proxy").toBe(200);
    const ip = limitOf(list.headers());
    expect(ip === 0 || ip >= RELAXED, `Per-IP rate limit is ${ip}/min.\n${hint}`).toBeTruthy();

    const created = await api.post(backend("/flows"), { data: { name: testName("preflight") } });
    if (created.status() === 409) {
      const body = await created.json();
      expect(
        body.code,
        "This user already has the maximum number of flows (MAX_FLOWS_PER_USER). Delete some, or raise the limit.",
      ).not.toBe("flow_limit_reached");
    }
    expect(created.status(), `Creating a flow failed.\n${hint}`).toBe(201);
    const writes = limitOf(created.headers());
    await api.delete(backend(`/flows/${(await created.json()).id}`));
    expect(
      writes === 0 || writes >= RELAXED,
      `Per-user write limit is ${writes}/min.\n${hint}`,
    ).toBeTruthy();
  } finally {
    await api.dispose();
  }
});
