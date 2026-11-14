import { expect, test } from "@playwright/test";

import { adminCredentials } from "../../support/env";

test("the account page shows who is signed in", async ({ page }) => {
  await page.goto("/settings/account");
  await expect(page.getByRole("heading", { name: "Account", level: 2 })).toBeVisible();
  await expect(page.getByText(adminCredentials().email)).toBeVisible();
});
