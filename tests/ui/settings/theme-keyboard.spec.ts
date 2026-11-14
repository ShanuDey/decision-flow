import { expect, test } from "../../support/fixtures";

test("the account menu theme options work from the keyboard", async ({ editor }) => {
  await editor.getByRole("button", { name: "Account menu" }).focus();
  await editor.keyboard.press("Enter");
  const dark = editor.getByRole("menuitemradio", { name: "Dark" });
  await expect(dark).toBeVisible();
  for (let i = 0; i < 8 && !(await dark.evaluate((el) => el === document.activeElement)); i++) {
    await editor.keyboard.press("ArrowDown");
  }
  await expect(dark).toBeFocused();
  await editor.keyboard.press("Enter");
  await expect(editor.locator("html")).toHaveClass(/dark/);
  await editor.getByRole("menuitemradio", { name: "Light" }).click();
  await expect(editor.locator("html")).not.toHaveClass(/dark/);
});
