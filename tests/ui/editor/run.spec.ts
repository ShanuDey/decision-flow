import { expect, test } from "../../support/fixtures";

test("a blank flow validates and test-runs from the top bar", async ({ editor }) => {
  await editor.getByRole("button", { name: "Run", exact: true }).click();
  const dialog = editor.getByRole("dialog", { name: "Test run" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Run", exact: true }).click();
  await expect(editor.getByRole("tab", { name: "Output" })).toBeVisible();
  await expect(editor.getByText("Succeeded")).toBeVisible();
});
