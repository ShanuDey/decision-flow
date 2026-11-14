import { addNode, saveState } from "../../support/editor";
import { expect, test } from "../../support/fixtures";

test("a blank flow is valid", async ({ editor }) => {
  await editor.getByRole("button", { name: /Validate/ }).click();
  await expect(editor.getByText("The flow is valid.")).toBeVisible();
});

test("problems are listed, and clicking one selects its node", async ({ editor }) => {
  await addNode(editor, "cond", /Condition/);
  await editor.locator(".react-flow__pane").click({ position: { x: 20, y: 300 } });
  await editor.getByRole("button", { name: /Validate/ }).click();
  await expect(editor.getByText(/Validation · \d+ problems?/)).toBeVisible();
  await expect(saveState(editor, "Saved")).toBeVisible();

  await editor.getByRole("button", { name: /Condition/ }).first().click();
  await expect(
    editor.getByRole("complementary", { name: "Settings" }).getByRole("heading", { name: "Condition", level: 2 }),
  ).toBeVisible();
});

test("Run is blocked by problems and shows them instead of the run dialog", async ({ editor }) => {
  await addNode(editor, "cond", /Condition/);
  await editor.getByRole("button", { name: "Run", exact: true }).click();
  await expect(editor.getByText(/Validation · \d+ problems?/)).toBeVisible();
  await expect(editor.getByRole("dialog", { name: "Test run" })).toHaveCount(0);
});

test("when validation cannot run, it says so instead of calling the flow valid", async ({ editor }) => {
  await editor.route("**/backend/flows/*/validate", (route) =>
    route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ code: "boom", message: "Server error", details: {} }),
    }),
  );
  await editor.getByRole("button", { name: /Validate/ }).click();
  await expect(editor.getByText("Could not validate")).toBeVisible();
  await expect(editor.getByText("The flow is valid.")).toHaveCount(0);
});

test("Run does nothing more when validation cannot run", async ({ editor }) => {
  await editor.route("**/backend/flows/*/validate", (route) =>
    route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ code: "boom", message: "Server error", details: {} }),
    }),
  );
  await editor.getByRole("button", { name: "Run", exact: true }).click();
  await expect(editor.getByText("Could not validate")).toBeVisible();
  await expect(editor.getByRole("dialog", { name: "Test run" })).toHaveCount(0);
  await expect(editor.getByText("The flow is valid.")).toHaveCount(0);
});
