import { testName } from "../../support/env";
import { expect, test } from "../../support/fixtures";
import { createFlowViaUi, deleteFlowViaUi } from "../../support/ui";

test("lists a flow, finds it by search, and clears the search", async ({ page, flow }) => {
  await page.goto("/flows");
  await expect(page.getByRole("heading", { name: "Flows", level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: flow.name })).toBeVisible();

  await page.getByRole("textbox", { name: "Search flows" }).fill(flow.name);
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page).toHaveURL(/q=/);
  await expect(page.getByRole("link", { name: flow.name })).toBeVisible();

  await page.getByRole("textbox", { name: "Search flows" }).fill("no-such-flow-anywhere");
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page.getByText(/No flows match/)).toBeVisible();

  await page.getByRole("link", { name: "Clear" }).click();
  await expect(page.getByRole("link", { name: flow.name })).toBeVisible();
});

test("creates a flow from the New flow dialog and opens its editor", async ({ page }) => {
  const name = testName("created");
  await page.goto("/flows");
  await createFlowViaUi(page, name);
  await expect(page.getByRole("navigation", { name: "Breadcrumb" })).toContainText(name);
  await deleteFlowViaUi(page, name);
});

test("renames a flow from its row menu", async ({ page, flow }) => {
  const renamed = `${flow.name} renamed`;
  await page.goto("/flows");
  await page.getByRole("button", { name: `Actions for ${flow.name}` }).click();
  await page.getByRole("menuitem", { name: "Rename" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("textbox").fill(renamed);
  await dialog.getByRole("button", { name: /Rename|Save/ }).click();
  await expect(page.getByRole("link", { name: renamed })).toBeVisible();
});

test("deletes a flow from its row menu", async ({ page }) => {
  const name = testName("to delete");
  await page.goto("/flows");
  await createFlowViaUi(page, name);
  await deleteFlowViaUi(page, name);
});

test("sorting by name is reflected in the URL", async ({ page, flow }) => {
  await page.goto("/flows");
  await expect(page.getByRole("link", { name: flow.name })).toBeVisible();
  await page.getByRole("link", { name: "Sort by Name" }).click();
  await expect(page).toHaveURL(/sort=name/);
});
