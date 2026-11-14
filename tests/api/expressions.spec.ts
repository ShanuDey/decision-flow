import { type APIRequestContext, expect, test } from "@playwright/test";

import { backend, signedInApi } from "../support/api";

let api: APIRequestContext;

test.beforeAll(async () => {
  api = await signedInApi();
});

test.afterAll(async () => {
  await api?.dispose();
});

const evaluate = async (data: Record<string, unknown>) => {
  const response = await api.post(backend("/expressions/evaluate"), { data });
  expect(response.status()).toBe(200);
  return response.json();
};

test("checks an expression without evaluating it", async () => {
  expect(await evaluate({ source: "input.score > 650 && input.income > 30000" })).toMatchObject({
    valid: true,
    return_type: "BOOL",
    result: null,
  });
});

test("evaluates an expression against a sample scope", async () => {
  const body = await evaluate({
    source: "input.score > 650 && input.income > 30000",
    scope: { input: { score: 700, income: 52000 } },
  });
  expect(body).toMatchObject({ valid: true, result: true });
});

test("reports a syntax error instead of failing the request", async () => {
  const body = await evaluate({ source: "input.score >" });
  expect(body.valid).toBe(false);
  expect(body.error).toBeTruthy();
});

test("renders and checks templates", async () => {
  const ok = await evaluate({
    kind: "template",
    source: "{{ vars.total }}",
    scope: { vars: { total: 3 } },
  });
  expect(ok).toMatchObject({ valid: true, result: 3 });

  const missing = await evaluate({ kind: "template", source: "{{ vars.total }}", scope: { vars: {} } });
  expect(missing.valid).toBe(false);
  expect(missing.error).toContain("not set");
});

test("rejects an expression over the length limit", async () => {
  const response = await api.post(backend("/expressions/evaluate"), {
    data: { source: "1".repeat(2001) },
  });
  expect(response.status()).toBe(422);
});
