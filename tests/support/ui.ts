import { expect, type Page } from "@playwright/test";

import { adminCredentials } from "./env";

export async function login(page: Page): Promise<void> {
  const { email, password } = adminCredentials();
  await page.goto("/login");
  await page.locator("#email").fill(email);
  await page.locator("#password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/flows$/);
}

export async function createFlowViaUi(page: Page, name: string): Promise<void> {
  await page.getByRole("button", { name: "New flow" }).click();
  await page.locator("#flow-name").fill(name);
  await page.getByRole("button", { name: "Create flow" }).click();
  await page.waitForURL(/\/flows\/[\w-]+$/);
  await expect(page.getByRole("button", { name: "Add node" })).toBeVisible();
}

export async function deleteFlowViaUi(page: Page, name: string): Promise<void> {
  await page.goto("/flows");
  await page.getByRole("button", { name: `Actions for ${name}` }).click();
  await page.getByRole("menuitem", { name: "Delete" }).click();
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(page.getByRole("button", { name: `Actions for ${name}` })).toHaveCount(0);
}
