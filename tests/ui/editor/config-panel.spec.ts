import { addNode, settingsPanel } from "../../support/editor";
import { expect, test } from "../../support/fixtures";

test("shows the selected node with a badge and Settings, Test and Docs tabs", async ({ editor }) => {
  await addNode(editor, "cond", /Condition/);
  const panel = settingsPanel(editor);
  await expect(panel.getByRole("heading", { name: "Condition", level: 2 })).toBeVisible();
  await expect(panel.getByText("Built-in")).toBeVisible();
  for (const tab of ["Settings", "Test", "Docs"]) {
    await expect(panel.getByRole("tab", { name: tab })).toBeVisible();
  }
});

test("the Docs tab describes the node", async ({ editor }) => {
  await addNode(editor, "cond", /Condition/);
  const panel = settingsPanel(editor);
  await panel.getByRole("tab", { name: "Docs" }).click();
  await expect(panel.getByText("Branch on a true/false expression")).toBeVisible();
  await expect(panel.getByText("true, false")).toBeVisible();
});

test("the Test tab evaluates the condition against sample input", async ({ editor }) => {
  await addNode(editor, "cond", /Condition/);
  const panel = settingsPanel(editor);
  await panel.getByRole("combobox").first().fill("1 > 0");
  await panel.getByRole("tab", { name: "Test" }).click();
  await panel.getByRole("button", { name: "Run test" }).click();
  await expect(panel.getByTestId("test-result")).toHaveText("true");
});

test("renaming a node updates it on the canvas", async ({ editor }) => {
  await addNode(editor, "cond", /Condition/);
  await editor.locator("#node-name").fill("Score gate");
  await expect(editor.locator(".react-flow__node", { hasText: "Score gate" })).toBeVisible();
});

test("Delete node removes it and Undo brings it back", async ({ editor }) => {
  await addNode(editor, "cond", /Condition/);
  await settingsPanel(editor).getByRole("button", { name: "Delete node" }).click();
  await expect(editor.locator(".react-flow__node", { hasText: "Condition" })).toHaveCount(0);
  await editor.getByRole("button", { name: "Undo" }).click();
  await expect(editor.locator(".react-flow__node", { hasText: "Condition" })).toBeVisible();
});

test("with nothing selected the panel offers flow variables", async ({ editor }) => {
  await editor.locator(".react-flow__pane").click({ position: { x: 20, y: 300 } });
  const panel = settingsPanel(editor);
  await expect(panel.getByText("Select a node to edit its settings.")).toBeVisible();
  await expect(panel.getByRole("button", { name: "Add variable" })).toBeVisible();
});
