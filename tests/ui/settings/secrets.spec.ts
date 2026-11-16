import { expect, test } from "@playwright/test";

const VALUE = "e2e-secret-value-1";

test("the Secrets page is in the settings navigation", async ({ page }) => {
  await page.goto("/settings/appearance");
  await page.getByRole("navigation", { name: "Settings" }).getByRole("link", { name: "Secrets" }).click();
  await expect(page).toHaveURL(/\/settings\/secrets$/);
  await expect(page.getByRole("heading", { name: "Secrets", level: 2 })).toBeVisible();
});

test("a secret can be added, replaced and deleted, and its value never appears", async ({ page }) => {
  const name = `E2E_KEY_${Date.now()}`;
  await page.goto("/settings/secrets");

  await page.getByRole("button", { name: "Add secret" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Name").fill(name.toLowerCase());
  await expect(dialog.getByLabel("Name")).toHaveValue(name);
  await dialog.getByLabel("Value").fill(VALUE);
  await dialog.getByRole("button", { name: "Save" }).click();

  const row = page.getByRole("row", { name: new RegExp(name) });
  await expect(row).toBeVisible();
  await expect(page.getByText(VALUE)).toHaveCount(0);

  await row.getByRole("button", { name: "Replace" }).click();
  await dialog.getByLabel("Value").fill("e2e-secret-value-2");
  await dialog.getByRole("button", { name: "Replace" }).click();
  await expect(page.getByText("Replaced " + name)).toBeVisible();
  await expect(page.getByText("e2e-secret-value-2")).toHaveCount(0);

  await row.getByRole("button", { name: "Delete" }).click();
  await dialog.getByRole("button", { name: "Delete" }).click();
  await expect(row).toHaveCount(0);
});

test("the value is hidden until Show value is pressed, and hidden again on reopen", async ({ page }) => {
  await page.goto("/settings/secrets");
  await page.getByRole("button", { name: "Add secret" }).click();
  const dialog = page.getByRole("dialog");
  const value = dialog.getByLabel("Value");

  await value.fill(VALUE);
  await expect(value).toHaveAttribute("type", "password");
  await dialog.getByRole("button", { name: "Show value" }).click();
  await expect(value).toHaveAttribute("type", "text");
  await dialog.getByRole("button", { name: "Hide value" }).click();
  await expect(value).toHaveAttribute("type", "password");

  await dialog.getByRole("button", { name: "Show value" }).click();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Add secret" }).click();
  await expect(dialog.getByLabel("Value")).toHaveAttribute("type", "password");
  await expect(dialog.getByLabel("Value")).toHaveValue("");
});

test("Save stays disabled until the name and value are valid", async ({ page }) => {
  await page.goto("/settings/secrets");
  await page.getByRole("button", { name: "Add secret" }).click();
  const dialog = page.getByRole("dialog");
  const save = dialog.getByRole("button", { name: "Save" });

  await expect(save).toBeDisabled();
  await dialog.getByLabel("Name").fill("1bad");
  await dialog.getByLabel("Value").fill(VALUE);
  await expect(save).toBeDisabled();
  await dialog.getByLabel("Name").fill("GOOD_NAME");
  await dialog.getByLabel("Value").fill("short");
  await expect(save).toBeDisabled();
  await dialog.getByLabel("Value").fill(VALUE);
  await expect(save).toBeEnabled();
});
