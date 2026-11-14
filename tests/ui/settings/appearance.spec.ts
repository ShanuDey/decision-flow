import { expect, test } from "@playwright/test";

test("the theme picker switches the theme and remembers it after a reload", async ({ page }) => {
  await page.goto("/settings/appearance");
  const theme = page.getByRole("radiogroup", { name: "Theme" });

  await theme.getByText("Dark").click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.reload();
  await expect(page.locator("html")).toHaveClass(/dark/);

  await theme.getByText("Light").click();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
});
