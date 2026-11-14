import type { Page } from "@playwright/test";

import { addNode } from "../../support/editor";
import { expect, test } from "../../support/fixtures";

// Limit errors are mocked in the browser, so these tests do not depend on the stack's real limits.
const limitError = (status: number, body: Record<string, unknown>, headers: Record<string, string> = {}) => ({
  status,
  headers,
  contentType: "application/json",
  body: JSON.stringify(body),
});

const rateLimited = (details: Record<string, unknown> = {}) =>
  limitError(
    429,
    {
      code: "rate_limited",
      message: "Too many requests; try again in 12 seconds",
      details: { scope: "user", limit: 60, retry_after: 12, ...details },
    },
    { "retry-after": "12" },
  );

async function failCreate(page: Page, response: ReturnType<typeof limitError>) {
  await page.route("**/backend/flows", (route) =>
    route.request().method() === "POST" ? route.fulfill(response) : route.continue(),
  );
}

async function tryCreate(page: Page) {
  await page.goto("/flows");
  await page.getByRole("button", { name: "New flow" }).click();
  await page.locator("#flow-name").fill("e2e limit check");
  await page.getByRole("button", { name: "Create flow" }).click();
}

test("creating a flow while rate limited explains the wait", async ({ page }) => {
  await failCreate(page, rateLimited());
  await tryCreate(page);
  await expect(page.getByText("Could not create the flow")).toBeVisible();
  await expect(page.getByText("You're going a bit fast. Try again in 12 seconds.")).toBeVisible();
});

test("reaching the flow limit says how to get under it", async ({ page }) => {
  await failCreate(
    page,
    limitError(409, {
      code: "flow_limit_reached",
      message: "You have 20 flows; the limit is 20.",
      details: { limit: 20, count: 20 },
    }),
  );
  await tryCreate(page);
  await expect(
    page.getByText("You have reached the limit of 20 flows. Delete a flow to create a new one."),
  ).toBeVisible();
});

test("a configured notice and link are shown, and unsafe links are not", async ({ page }) => {
  await failCreate(
    page,
    rateLimited({ notice: "This is a free demo on shared resources.", notice_url: "https://example.com/sponsor" }),
  );
  await tryCreate(page);
  await expect(page.getByText("This is a free demo on shared resources.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Learn more" })).toHaveAttribute(
    "href",
    "https://example.com/sponsor",
  );
});

test("an unsafe notice link is dropped", async ({ page }) => {
  await failCreate(page, rateLimited({ notice: "Free demo.", notice_url: "javascript:alert(1)" }));
  await tryCreate(page);
  await expect(page.getByText("Free demo.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Learn more" })).toHaveCount(0);
});

test("saving in the editor while rate limited keeps the change and explains why", async ({ editor }) => {
  await editor.route("**/backend/flows/*/draft", (route) => route.fulfill(rateLimited()));
  await addNode(editor, "cond", /Condition/);
  await editor.getByRole("button", { name: "Save", exact: true }).click();
  await expect(editor.getByText("Could not save")).toBeVisible();
  await expect(editor.getByText("You're going a bit fast. Try again in 12 seconds.")).toBeVisible();
  await expect(editor.getByRole("status").filter({ hasText: "Unsaved changes" })).toBeVisible();
  await expect(editor.locator(".react-flow__node", { hasText: "Condition" })).toBeVisible();
});

test("running while the server is busy explains the wait", async ({ editor }) => {
  await editor.route("**/backend/flows/*/runs", (route) =>
    route.fulfill(
      limitError(
        429,
        { code: "run_limit", message: "Too many runs are in progress", details: { scope: "app", limit: 10 } },
        { "retry-after": "3" },
      ),
    ),
  );
  await editor.getByRole("button", { name: "Run", exact: true }).click();
  const dialog = editor.getByRole("dialog", { name: "Test run" });
  await dialog.getByRole("button", { name: "Run", exact: true }).click();
  await expect(dialog.getByRole("alert")).toHaveText(
    "The server is busy running other flows. Try again in 3 seconds.",
  );
});
