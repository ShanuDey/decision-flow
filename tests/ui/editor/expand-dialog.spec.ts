import { addNode, settingsPanel } from "../../support/editor";
import { expect, test } from "../../support/fixtures";

test.beforeEach(async ({ editor }) => {
  await addNode(editor, "cond", /Condition/);
  await settingsPanel(editor).getByRole("button", { name: "Expand Expression editor" }).click();
});

test("opens one field in a large dialog and writes back live", async ({ editor }) => {
  const dialog = editor.getByRole("dialog");
  await expect(dialog.getByText("Available data")).toBeVisible();
  await dialog.locator(".cm-content").click();
  await editor.keyboard.type("1 > 0");
  await dialog.getByRole("button", { name: "Done" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(settingsPanel(editor).getByRole("combobox").first()).toHaveValue("1 > 0");
});

test("the strip says whether the expression is valid", async ({ editor }) => {
  const strip = editor.getByRole("dialog").getByTestId("check-strip");
  await editor.getByRole("dialog").locator(".cm-content").click();
  await editor.keyboard.type("1 > 0");
  await expect(strip).toContainText("Valid expression");
  await editor.keyboard.type(" >");
  await expect(strip).not.toContainText("Valid expression");
  await editor.keyboard.press("Backspace");
  await editor.keyboard.press("Backspace");
  await expect(strip).toContainText("Valid expression");
});

test("Run test evaluates the expression against sample input", async ({ editor }) => {
  const dialog = editor.getByRole("dialog");
  await dialog.locator(".cm-content").click();
  await editor.keyboard.type("1 > 0");
  await dialog.getByRole("button", { name: "Run test" }).click();
  await expect(dialog.getByTestId("test-result")).toHaveText("true");
});

test("Escape closes the dialog and keeps the text", async ({ editor }) => {
  const dialog = editor.getByRole("dialog");
  await dialog.locator(".cm-content").click();
  await editor.keyboard.type("2 > 1");
  await editor.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(settingsPanel(editor).getByRole("combobox").first()).toHaveValue("2 > 1");
});

test("when the check request fails, the strip says it could not check", async ({ editor }) => {
  await editor.route("**/backend/expressions/evaluate", (route) =>
    route.fulfill({
      status: 429,
      contentType: "application/json",
      headers: { "retry-after": "5" },
      body: JSON.stringify({ code: "rate_limited", message: "slow down", details: { scope: "ip" } }),
    }),
  );
  const dialog = editor.getByRole("dialog");
  await dialog.locator(".cm-content").click();
  await editor.keyboard.type("1 > 0");
  await expect(dialog.getByTestId("check-strip")).toHaveText("Could not check the expression.");
});

test("typing does not send a request per keystroke", async ({ editor }) => {
  let calls = 0;
  await editor.route("**/backend/expressions/evaluate", (route) => {
    calls += 1;
    return route.continue();
  });
  const dialog = editor.getByRole("dialog");
  await dialog.locator(".cm-content").click();
  await editor.keyboard.type("input.score > 650", { delay: 40 });
  await expect(dialog.getByTestId("check-strip")).not.toHaveText("Checking…");
  expect(calls).toBeLessThanOrEqual(2);
});

test("Reset sample restores the generated sample input", async ({ editor }) => {
  const dialog = editor.getByRole("dialog");
  const sample = dialog.getByLabel("Sample input");
  const original = await sample.inputValue();
  await sample.fill("{}");
  await dialog.getByRole("button", { name: "Reset sample" }).click();
  await expect(sample).toHaveValue(original);
});
