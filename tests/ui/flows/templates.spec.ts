import { testName } from "../../support/env";
import { expect, test } from "../../support/fixtures";
import { deleteFlowViaUi } from "../../support/ui";

test("creates a flow from a template and opens its editor", async ({ page }) => {
  const name = testName("lead");
  await page.goto("/flows");
  await page.getByRole("button", { name: "New flow" }).click();
  await page.getByRole("textbox", { name: "Search templates" }).fill("lead");
  await page.getByRole("option", { name: /Lead scoring/ }).click();
  await page.locator("#flow-name").fill(name);
  await page.getByRole("button", { name: "Create flow" }).click();
  await page.waitForURL(/\/flows\/[\w-]+$/);
  await expect(page.getByRole("navigation", { name: "Breadcrumb" })).toContainText(name);
  await expect(page.locator(".react-flow__node", { hasText: "Hot?" })).toBeVisible();
  await deleteFlowViaUi(page, name);
});

test("a template stays selected when a search hides it", async ({ page }) => {
  await page.goto("/flows");
  await page.getByRole("button", { name: "New flow" }).click();
  await page.getByRole("option", { name: /Loan eligibility/ }).click();
  await expect(page.locator("#flow-name")).toHaveValue("Loan eligibility");
  await page.getByRole("textbox", { name: "Search templates" }).fill("no-such-template");
  await expect(page.getByText("No templates match your search.")).toBeVisible();
  await expect(page.locator("#flow-name")).toHaveValue("Loan eligibility");
  await expect(page.getByRole("heading", { name: "Loan eligibility", level: 3 })).toBeVisible();
});

test("Enter in the search box selects a match and does not create a flow", async ({ page }) => {
  await page.goto("/flows");
  await page.getByRole("button", { name: "New flow" }).click();
  await page.getByRole("textbox", { name: "Search templates" }).fill("discount");
  await page.keyboard.press("Enter");
  await expect(page.locator("#flow-name")).toHaveValue("Discount tier");
  await expect(page).toHaveURL(/\/flows$/);
});

test("a typed name survives picking another template", async ({ page }) => {
  await page.goto("/flows");
  await page.getByRole("button", { name: "New flow" }).click();
  await page.locator("#flow-name").fill("My own name");
  await page.getByRole("option", { name: /Lead scoring/ }).click();
  await expect(page.locator("#flow-name")).toHaveValue("My own name");
});
