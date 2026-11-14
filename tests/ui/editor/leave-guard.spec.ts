import { addNode, saveState } from "../../support/editor";
import { expect, test } from "../../support/fixtures";

const prompt = (page: import("@playwright/test").Page) =>
  page.getByRole("dialog", { name: "Save changes before leaving?" });

test("leaving a clean flow needs no prompt", async ({ editor }) => {
  await editor.getByRole("link", { name: "Back to flows" }).click();
  await editor.waitForURL(/\/flows$/);
});

test("Cancel keeps you in the editor with the change intact", async ({ editor, flow }) => {
  await addNode(editor, "cond", /Condition/);
  await editor.getByRole("link", { name: "Back to flows" }).click();
  await expect(prompt(editor)).toBeVisible();
  await prompt(editor).getByRole("button", { name: "Cancel" }).click();
  await expect(editor).toHaveURL(new RegExp(`${flow.url}$`));
  await expect(editor.locator(".react-flow__node", { hasText: "Condition" })).toBeVisible();
});

test("Discard leaves without saving", async ({ editor, page, flow }) => {
  await addNode(editor, "cond", /Condition/);
  await editor.getByRole("link", { name: "Back to flows" }).click();
  await prompt(editor).getByRole("button", { name: "Discard" }).click();
  await editor.waitForURL(/\/flows$/);
  await page.goto(flow.url);
  await expect(page.getByRole("button", { name: "Add node" })).toBeVisible();
  await expect(page.locator(".react-flow__node", { hasText: "Condition" })).toHaveCount(0);
});

test("Save and leave keeps the change", async ({ editor, page, flow }) => {
  await addNode(editor, "cond", /Condition/);
  await editor.getByRole("button", { name: "Account menu" }).click();
  await editor.getByRole("menuitem", { name: "Settings" }).click();
  await prompt(editor).getByRole("button", { name: "Save and leave" }).click();
  await editor.waitForURL(/\/settings\/appearance\?from=/);
  await page.goto(flow.url);
  await expect(page.locator(".react-flow__node", { hasText: "Condition" })).toBeVisible();
});

test("Ctrl+S saves and the change survives a reload", async ({ editor }) => {
  await addNode(editor, "cond", /Condition/);
  await editor.keyboard.press("Control+s");
  await expect(saveState(editor, "Saved")).toBeVisible();
  await editor.reload();
  await expect(editor.locator(".react-flow__node", { hasText: "Condition" })).toBeVisible();
});
