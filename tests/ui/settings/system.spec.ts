import { expect, test } from "@playwright/test";

test("the system page reports the status of the API, Postgres and MLflow", async ({ page }) => {
  await page.goto("/settings/system");
  const status = page.getByRole("region", { name: /status/i });
  for (const service of ["API", "Postgres", "MLflow"]) {
    await expect(status.getByText(service, { exact: true })).toBeVisible();
  }
});
