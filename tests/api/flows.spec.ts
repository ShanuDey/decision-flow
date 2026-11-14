import { type APIRequestContext, expect, request, test } from "@playwright/test";

import { backend, signedInApi } from "../support/api";
import { baseURL, testName } from "../support/env";

let api: APIRequestContext;

test.beforeAll(async () => {
  api = await signedInApi();
});

test.afterAll(async () => {
  await api?.dispose();
});

test("requests without a session are rejected", async () => {
  const anonymous = await request.newContext({ baseURL });
  const response = await anonymous.get(backend("/flows"));
  expect([401, 403]).toContain(response.status());
  await anonymous.dispose();
});

test("flow lifecycle: create, rename, save a draft, validate, run, delete", async () => {
  const created = await api.post(backend("/flows"), { data: { name: testName("api") } });
  expect(created.status()).toBe(201);
  const flow = await created.json();
  const id: string = flow.id;
  expect(flow.draft_version).toBe(1);

  try {
    const renamed = await api.patch(backend(`/flows/${id}`), { data: { name: `${flow.name} renamed` } });
    expect(renamed.status()).toBe(200);
    expect((await renamed.json()).name).toBe(`${flow.name} renamed`);

    const fetched = await (await api.get(backend(`/flows/${id}`))).json();
    expect(fetched.draft.nodes.map((n: { type: string }) => n.type)).toEqual(["start", "end"]);

    const missingMatch = await api.put(backend(`/flows/${id}/draft`), { data: fetched.draft });
    expect(missingMatch.status()).toBe(428);

    const saved = await api.put(backend(`/flows/${id}/draft`), {
      data: fetched.draft,
      headers: { "if-match": "1" },
    });
    expect(saved.status()).toBe(200);
    expect((await saved.json()).draft_version).toBe(2);

    const stale = await api.put(backend(`/flows/${id}/draft`), {
      data: fetched.draft,
      headers: { "if-match": "1" },
    });
    expect(stale.status()).toBe(409);

    const validated = await api.post(backend(`/flows/${id}/validate`));
    expect(validated.status()).toBe(200);
    expect(await validated.json()).toEqual({ valid: true });

    const run = await api.post(backend(`/flows/${id}/runs`), { data: { test: true, input: {} } });
    expect(run.status()).toBe(200);
    expect((await run.json()).status).toBe("succeeded");
  } finally {
    const deleted = await api.delete(backend(`/flows/${id}`));
    expect(deleted.status()).toBe(204);
  }

  expect((await api.get(backend(`/flows/${id}`))).status()).toBe(404);
});

test("an invalid draft is saved but fails validation with a node-level issue", async () => {
  const flow = await (await api.post(backend("/flows"), { data: { name: testName("api invalid") } })).json();
  try {
    const draft = structuredClone(flow.draft);
    draft.nodes.push({
      id: "orphan",
      type: "condition",
      name: "Orphan",
      position: { x: 0, y: 200 },
      data: { expression: "1 > 0" },
    });
    const saved = await api.put(backend(`/flows/${flow.id}/draft`), {
      data: draft,
      headers: { "if-match": "1" },
    });
    expect(saved.status()).toBe(200);

    const validated = await api.post(backend(`/flows/${flow.id}/validate`));
    expect(validated.status()).toBe(422);
    const body = await validated.json();
    expect(body.code).toBe("invalid_flow");
    expect(body.details.errors.length).toBeGreaterThan(0);
  } finally {
    await api.delete(backend(`/flows/${flow.id}`));
  }
});
