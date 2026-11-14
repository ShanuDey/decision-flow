import { addNode, saveState } from "../../support/editor";
import { expect, test } from "../../support/fixtures";

test("searching narrows the list and Enter adds the node", async ({ editor }) => {
  await editor.getByRole("button", { name: "Add node" }).click();
  await editor.getByRole("textbox", { name: "Search nodes" }).fill("cond");
  await expect(editor.getByRole("option", { name: /Condition/ })).toBeVisible();
  await expect(editor.getByRole("option", { name: /^Start/ })).toHaveCount(0);
  await editor.keyboard.press("Enter");
  await expect(editor.locator(".react-flow__node", { hasText: "Condition" })).toBeVisible();
  await expect(saveState(editor, "Unsaved changes")).toBeVisible();
});

test("the tabs filter by source and Community is empty for now", async ({ editor }) => {
  await editor.getByRole("button", { name: "Add node" }).click();
  await editor.getByRole("tab", { name: "Community" }).click();
  await expect(editor.getByText("No community nodes installed yet.")).toBeVisible();
  await editor.getByRole("tab", { name: "Built-in" }).click();
  await expect(editor.getByRole("option", { name: /Assign values/ })).toBeVisible();
  await editor.getByRole("tab", { name: "All" }).click();
  await editor.keyboard.press("Enter");
  await expect(editor.locator(".react-flow__node", { hasText: /Start|End|Assign|Condition/ }).first()).toBeVisible();
});

test("a node that is already in the flow cannot be added again", async ({ editor }) => {
  await editor.getByRole("button", { name: "Add node" }).click();
  await editor.getByRole("textbox", { name: "Search nodes" }).fill("start");
  await expect(editor.getByRole("option", { name: /^Start/ })).toHaveAttribute("aria-disabled", "true");
  await expect(editor.getByText("Already in the flow.")).toBeVisible();
});

test("the + on an unconnected output adds and connects the next node", async ({ editor }) => {
  await addNode(editor, "cond", /Condition/);
  await editor.getByRole("button", { name: "Add node after true" }).click();
  await editor.getByRole("option", { name: /Assign values/ }).click();
  await expect(editor.locator(".react-flow__node", { hasText: "Assign values" })).toBeVisible();
  await expect(editor.locator(".react-flow__edge")).toHaveCount(2);
});

test("Add node places the node inside the visible canvas, even after panning far away", async ({ editor }) => {
  const pane = editor.locator(".react-flow__pane");
  const box = (await pane.boundingBox())!;
  await editor.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await editor.mouse.down();
  await editor.mouse.move(box.x + box.width / 2 - 900, box.y + box.height / 2 + 300, { steps: 10 });
  await editor.mouse.up();

  await addNode(editor, "cond", /Condition/);
  const node = editor.locator(".react-flow__node", { hasText: "Condition" });
  const n = (await node.boundingBox())!;
  const view = (await editor.locator(".react-flow").boundingBox())!;
  expect(n.x).toBeGreaterThanOrEqual(view.x);
  expect(n.y).toBeGreaterThanOrEqual(view.y);
  expect(n.x + n.width).toBeLessThanOrEqual(view.x + view.width);
  expect(n.y + n.height).toBeLessThanOrEqual(view.y + view.height);
  const centerX = n.x + n.width / 2;
  expect(Math.abs(centerX - (view.x + view.width / 2))).toBeLessThan(120);
});

test("adding several nodes in a row does not stack them", async ({ editor }) => {
  await addNode(editor, "assign", /Assign values/);
  await addNode(editor, "cond", /Condition/);
  const a = (await editor.locator(".react-flow__node", { hasText: "Assign values" }).boundingBox())!;
  const b = (await editor.locator(".react-flow__node", { hasText: "Condition" }).boundingBox())!;
  const overlap = a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
  expect(overlap).toBe(false);
});
