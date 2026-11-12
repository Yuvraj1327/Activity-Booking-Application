import { test as setup, expect } from "@playwright/test";
import { ADMIN, signIn } from "./support/helpers";

setup("sign in as the admin and keep the session", async ({ page }) => {
  await signIn(page, ADMIN.email, ADMIN.password);
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByTestId("admin-name")).toHaveText("Ada Admin");
  await page.context().storageState({ path: "e2e/.stack/admin.json" });
});
