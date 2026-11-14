import { expect, test } from "../../support/fixtures";

async function openMenu(page: import("@playwright/test").Page) {
  await page.getByRole("button", { name: "Account menu" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("menuitemradio", { name: "Dark" })).toBeVisible();
}

test("the theme options sit in one row, with exactly one selected", async ({ editor }) => {
  await openMenu(editor);
  const boxes = [];
  for (const name of ["Light", "Dark", "System"]) {
    boxes.push((await editor.getByRole("menuitemradio", { name }).boundingBox())!);
  }
  expect(Math.abs(boxes[0].y - boxes[1].y)).toBeLessThan(2);
  expect(Math.abs(boxes[1].y - boxes[2].y)).toBeLessThan(2);
  expect(boxes[0].x).toBeLessThan(boxes[1].x);
  expect(boxes[1].x).toBeLessThan(boxes[2].x);
  await expect(editor.locator('[role="menuitemradio"][aria-checked="true"]')).toHaveCount(1);
});

test("the theme options work from the keyboard with the arrow keys", async ({ editor }) => {
  await openMenu(editor);
  const options = ["Light", "Dark", "System"].map((name) =>
    editor.getByRole("menuitemradio", { name }),
  );
  const [light, dark, system] = options;

  await light.focus();
  await editor.keyboard.press("ArrowRight");
  await expect(dark).toBeFocused();
  await editor.keyboard.press("ArrowRight");
  await expect(system).toBeFocused();
  await editor.keyboard.press("ArrowRight");
  await expect(light).toBeFocused();
  await editor.keyboard.press("ArrowLeft");
  await expect(system).toBeFocused();
  await editor.keyboard.press("ArrowLeft");
  await expect(dark).toBeFocused();

  await editor.keyboard.press("Enter");
  await expect(editor.locator("html")).toHaveClass(/dark/);
  await expect(dark).toHaveAttribute("aria-checked", "true");
  await expect(editor.getByRole("menu")).toBeVisible();

  await light.click();
  await expect(editor.locator("html")).not.toHaveClass(/dark/);
});
