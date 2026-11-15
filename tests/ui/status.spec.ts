import { expect, test } from "@playwright/test";

test("the status page reports the status of the API, Postgres and MLflow", async ({ page }) => {
  await page.goto("/status");
  const status = page.getByRole("region", { name: /status/i });
  for (const service of ["API", "Postgres", "MLflow"]) {
    await expect(status.getByText(service, { exact: true })).toBeVisible();
  }
});

test.describe("signed out", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("the status page is public", async ({ page }) => {
    await page.goto("/status");
    await expect(page).toHaveURL(/\/status$/);
    await expect(page.getByRole("heading", { name: "System status" })).toBeVisible();
  });
});
