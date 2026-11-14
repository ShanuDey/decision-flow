import { expect, test } from "@playwright/test";

import { adminCredentials } from "../../support/env";

test.use({ storageState: { cookies: [], origins: [] } });

test("a signed-out visitor is sent to the login page", async ({ page }) => {
  await page.goto("/flows");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
});

test("a wrong password shows an error and stays on the login page", async ({ page }) => {
  await page.goto("/login");
  await page.locator("#email").fill(adminCredentials().email);
  await page.locator("#password").fill("definitely-not-the-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Invalid email or password.")).toBeVisible();
  await expect(page).toHaveURL(/\/login/);
});

test("valid credentials open the flows list, and sign out returns to login", async ({ page }) => {
  const { email, password } = adminCredentials();
  await page.goto("/login");
  await page.locator("#email").fill(email);
  await page.locator("#password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/flows$/);
  await expect(page.getByRole("heading", { name: "Flows", level: 1 })).toBeVisible();

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await page.waitForURL(/\/login/);
});
