import { addNode } from "../../support/editor";
import { expect, test } from "../../support/fixtures";

test("right-click on a node still offers its actions", async ({ editor }) => {
  await addNode(editor, "cond", /Condition/);
  await editor.locator(".react-flow__node", { hasText: "Condition" }).click({ button: "right" });
  const menu = editor.getByRole("menu");
  for (const item of ["Configure", "Rename", "Duplicate", "Delete"]) {
    await expect(menu.getByRole("menuitem", { name: new RegExp(item) })).toBeVisible();
  }
  await editor.keyboard.press("Escape");
  await expect(menu).toHaveCount(0);
});

test("right-click on a connection offers Delete connection", async ({ editor }) => {
  const edge = editor.locator(".react-flow__edge").first();
  await edge.locator("path").first().click({ button: "right", force: true });
  await expect(editor.getByRole("menuitem", { name: /Delete connection/ })).toBeVisible();
});

test("right-click on the empty canvas shows no custom menu", async ({ editor }) => {
  await editor.locator(".react-flow__pane").click({ button: "right", position: { x: 40, y: 400 } });
  await expect(editor.getByRole("menu")).toHaveCount(0);
  await expect(editor.getByText("Add node here")).toHaveCount(0);
  await expect(editor.getByText("Fit view")).toHaveCount(0);
});

test("a node menu still opens after right-clicking the empty canvas", async ({ editor }) => {
  await addNode(editor, "cond", /Condition/);
  await editor.locator(".react-flow__pane").click({ button: "right", position: { x: 40, y: 400 } });
  await editor.locator(".react-flow__node", { hasText: "Condition" }).click({ button: "right" });
  await expect(editor.getByRole("menu").getByRole("menuitem", { name: /Configure/ })).toBeVisible();
});
