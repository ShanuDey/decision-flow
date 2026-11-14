import { expect, type Page } from "@playwright/test";

export async function addNode(page: Page, search: string, label: RegExp): Promise<void> {
  await page.getByRole("button", { name: "Add node" }).click();
  await page.getByRole("textbox", { name: "Search nodes" }).fill(search);
  await page.keyboard.press("Enter");
  await expect(page.locator(".react-flow__node", { hasText: label })).toBeVisible();
}

export const settingsPanel = (page: Page) => page.getByRole("complementary", { name: "Settings" });

export const saveState = (page: Page, text: "Saved" | "Unsaved changes") =>
  page.getByRole("status").filter({ hasText: text });
