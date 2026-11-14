import { expect, test } from "../../support/fixtures";
import { saveState } from "../../support/editor";

test("shows the back link, breadcrumb, actions and account menu", async ({ editor, flow }) => {
  await expect(editor.getByRole("link", { name: "Back to flows" })).toBeVisible();
  await expect(editor.getByRole("navigation", { name: "Breadcrumb" })).toContainText(flow.name);
  for (const label of ["Save", "Run", "Account menu"]) {
    await expect(editor.getByRole("button", { name: label, exact: true })).toBeVisible();
  }
  await expect(editor.getByRole("button", { name: /Validate/ })).toBeVisible();
  await expect(saveState(editor, "Saved")).toBeVisible();
});

test("the avatar menu switches the theme from inside the editor", async ({ editor }) => {
  await editor.getByRole("button", { name: "Account menu" }).click();
  await editor.getByRole("menuitemradio", { name: "Dark" }).click();
  await expect(editor.locator("html")).toHaveClass(/dark/);
  await editor.getByRole("menuitemradio", { name: "Light" }).click();
  await expect(editor.locator("html")).not.toHaveClass(/dark/);
});

test("the avatar menu links to Settings with a way back to the flow", async ({ editor, flow }) => {
  await editor.getByRole("button", { name: "Account menu" }).click();
  await editor.getByRole("menuitem", { name: "Settings" }).click();
  await editor.waitForURL(/\/settings\/appearance\?from=/);
  await editor.getByRole("link", { name: "Back to flow" }).click();
  await editor.waitForURL(new RegExp(`${flow.url}$`));
});

test("the flow can be renamed from the breadcrumb", async ({ editor, flow }) => {
  await editor.getByRole("button", { name: flow.name }).click();
  const dialog = editor.getByRole("dialog", { name: "Rename flow" });
  await dialog.getByRole("textbox").fill(`${flow.name} v2`);
  await dialog.getByRole("button", { name: "Rename" }).click();
  await expect(editor.getByRole("navigation", { name: "Breadcrumb" })).toContainText(`${flow.name} v2`);
});
