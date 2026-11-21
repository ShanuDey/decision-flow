import { expect, type Page, test } from "@playwright/test";

const OPEN = "/docs/open";
const APP = "http://app.test";

// The saved app does not exist: answer its requests so a redirect to it has somewhere to land.
test.beforeEach(async ({ page }) => {
  await page.route(`${APP}/**`, (route) => route.fulfill({ contentType: "text/html", body: "<title>app</title>" }));
});

async function save(page: Page, address: string, to = "marketplace") {
  await page.goto(`${OPEN}?to=${to}`);
  await page.getByLabel("App address").fill(address);
  await page.getByRole("button", { name: "Continue" }).click();
}

test("the first visit asks for the app address", async ({ page }) => {
  await page.goto(`${OPEN}?to=marketplace`);
  await expect(page.getByLabel("App address")).toBeVisible();
  await expect(page).toHaveURL(/\/docs\/open/);
});

test("an address that is not http or https is refused with a message", async ({ page }) => {
  await page.goto(`${OPEN}?to=marketplace`);
  for (const bad of ["javascript:alert(1)", "ftp://example.com", "example.com", "https://user:pass@example.com"]) {
    await page.getByLabel("App address").fill(bad);
    await page.getByRole("button", { name: "Continue" }).click();
    await expect(page.getByRole("alert")).toContainText("Enter a full address");
    await expect(page).toHaveURL(/\/docs\/open/);
  }
});

test("a good address is saved, reduced to its origin, and opened at the target", async ({ page }) => {
  await save(page, `${APP}/ignored/path?x=1`);
  await page.waitForURL(`${APP}/marketplace`);
  await page.goto(`${OPEN}?change`);
  await expect(page.getByLabel("App address")).toHaveValue(APP);
});

test("a saved address is used without asking, for each target", async ({ page }) => {
  await save(page, APP);
  await page.waitForURL(`${APP}/marketplace`);
  await page.goto(`${OPEN}?to=connections`);
  await page.waitForURL(`${APP}/connections`);
  await page.goto(`${OPEN}?to=home`);
  await page.waitForURL(`${APP}/`);
});

test("a target that is not on the list opens the home page of the saved app", async ({ page }) => {
  await save(page, APP);
  await page.waitForURL(`${APP}/marketplace`);
  for (const to of ["%2F%2Fevil.test", "nope", "__proto__"]) {
    await page.goto(`${OPEN}?to=${to}`);
    await page.waitForURL(`${APP}/`);
  }
});

test("change shows the saved address to edit instead of redirecting", async ({ page }) => {
  await save(page, APP);
  await page.waitForURL(`${APP}/marketplace`);
  await page.goto(`${OPEN}?to=marketplace&change`);
  await expect(page.getByLabel("App address")).toHaveValue(APP);
  await page.getByLabel("App address").fill("http://other.test:8080");
  await page.route("http://other.test:8080/**", (route) => route.fulfill({ body: "other" }));
  await page.getByRole("button", { name: "Continue" }).click();
  await page.waitForURL("http://other.test:8080/marketplace");
});

test("with storage blocked it still asks and still opens the app", async ({ page }) => {
  await page.addInitScript(() => {
    const blocked = () => {
      throw new DOMException("blocked", "SecurityError");
    };
    if (location.pathname.startsWith("/docs/open")) {
      Storage.prototype.getItem = blocked;
      Storage.prototype.setItem = blocked;
    }
  });
  await save(page, APP);
  await page.waitForURL(`${APP}/marketplace`);
});

test("the page keeps the docs address out of the referrer", async ({ page }) => {
  await page.goto(OPEN);
  await expect(page.locator('meta[name="referrer"]')).toHaveAttribute("content", "no-referrer");
});

test("catalog and home buttons go through the page", async ({ page }) => {
  await page.goto("/docs/catalog/connection-types/github");
  await expect(page.getByRole("link", { name: "Open in your app" })).toHaveAttribute("href", `${OPEN}?to=marketplace`);
  await expect(page.getByRole("link", { name: "Get started" }).first()).toHaveAttribute("href", `${OPEN}?to=home`);
  await expect(page.getByRole("link", { name: "Use a different app address" })).toHaveAttribute(
    "href",
    `${OPEN}?to=marketplace&change`,
  );
});

test("a link clicked inside the app's docs frame opens the app in the whole window", async ({ page }) => {
  // Same origin as the docs, like the app's own /docs copy; the app refuses to be framed itself.
  await page.route("**/frame-host", (route) =>
    route.fulfill({ contentType: "text/html", body: '<iframe src="/docs/catalog/connection-types/github"></iframe>' }),
  );
  await save(page, APP);
  await page.waitForURL(`${APP}/marketplace`);
  await page.goto("/frame-host");
  await page.frameLocator("iframe").getByRole("link", { name: "Open in your app" }).click();
  await page.waitForURL(`${APP}/marketplace`);
});
