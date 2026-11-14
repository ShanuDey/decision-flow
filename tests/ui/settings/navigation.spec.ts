import { expect, test } from "@playwright/test";

test("settings opens on Appearance and the sub-navigation reaches every page", async ({ page }) => {
  await page.goto("/settings");
  await expect(page).toHaveURL(/\/settings\/appearance$/);

  const nav = page.getByRole("navigation", { name: "Settings" });
  await nav.getByRole("link", { name: "Account" }).click();
  await expect(page).toHaveURL(/\/settings\/account$/);
  await nav.getByRole("link", { name: "System" }).click();
  await expect(page).toHaveURL(/\/settings\/system$/);
  await nav.getByRole("link", { name: "Appearance" }).click();
  await expect(page).toHaveURL(/\/settings\/appearance$/);
});

test("Back to flow only appears when the settings page was opened from a flow", async ({ page }) => {
  await page.goto("/settings/appearance");
  await expect(page.getByRole("link", { name: "Back to flow" })).toHaveCount(0);
  await page.goto("/settings/appearance?from=/flows/abc-123");
  await expect(page.getByRole("link", { name: "Back to flow" })).toHaveAttribute(
    "href",
    "/flows/abc-123",
  );
  await page.goto("/settings/appearance?from=https://evil.example/x");
  await expect(page.getByRole("link", { name: "Back to flow" })).toHaveCount(0);
});
