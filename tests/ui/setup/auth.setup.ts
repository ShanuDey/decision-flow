import { test as setup } from "@playwright/test";

import { AUTH_FILE } from "../../support/env";
import { login } from "../../support/ui";

setup("sign in once and save the session", async ({ page }) => {
  await login(page);
  await page.context().storageState({ path: AUTH_FILE });
});
