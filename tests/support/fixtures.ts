import { expect, type Page, test as base } from "@playwright/test";

import { baseURL, testName } from "./env";

export interface FlowRef {
  id: string;
  name: string;
  url: string;
}

interface Fixtures {
  // A fresh flow created through the API and deleted after the test.
  flow: FlowRef;
  editor: Page;
}

const sameOrigin = { origin: baseURL };

export const test = base.extend<Fixtures>({
  flow: async ({ request }, use) => {
    const name = testName("flow");
    const created = await request.post("/backend/flows", {
      data: { name },
      headers: sameOrigin,
    });
    expect(created.status()).toBe(201);
    const { id } = await created.json();
    await use({ id, name, url: `/flows/${id}` });
    await request.delete(`/backend/flows/${id}`, { headers: sameOrigin });
  },

  editor: async ({ page, flow }, use) => {
    await page.goto(flow.url);
    await expect(page.getByRole("button", { name: "Add node" })).toBeVisible();
    await use(page);
  },
});

export { expect };
