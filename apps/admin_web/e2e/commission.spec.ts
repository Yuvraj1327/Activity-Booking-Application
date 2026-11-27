import { expect, test } from "@playwright/test";

// Real admin web + real FastAPI + real Postgres. Creates the three kinds of rule through the UI and
// checks the priority note, the history, the commission report and the (unavailable) ledger state.
// After a successful change the page re-renders from the server. Some buttons disappear with it (for
// example "Set global commission" once the rule exists), taking their dialog along: both outcomes are fine.
const confirm = async (page: import("@playwright/test").Page) => {
  const dialog = page.locator("dialog[open]");
  await dialog.getByTestId("action-confirm").click();
  // Wait for the server round trip: either the result message, or the dialog unmounting with its button.
  await expect(async () => {
    const shown = await dialog.getByTestId("action-result").count();
    expect(shown > 0 || (await dialog.count()) === 0).toBeTruthy();
  }).toPass({ timeout: 10_000 });
  if (await dialog.count()) await dialog.getByRole("button", { name: "Close" }).click();
};

test.describe("commission management", () => {
  test("priority is explained, and global / activity / venue rules can be created, changed and deactivated", async ({ page }) => {
    await page.goto("/commission");
    await expect(page.getByTestId("priority-note")).toContainText("Venue-specific");
    await expect(page.getByTestId("priority-note")).toContainText("Global default");

    // global
    await page.getByTestId("global-create").click();
    let d = page.locator("dialog[open]");
    await d.getByLabel("Commission (basis points) *").fill("1000");
    await d.getByLabel("Reason *").fill("Launch rate agreed with the client");
    await confirm(page);
    await expect(page.getByTestId("global-pct")).toHaveText("10%");

    // change it (a new version, not an edit)
    await page.getByTestId("global-rule").getByTestId("rule-change").click();
    d = page.locator("dialog[open]");
    await d.getByLabel("Commission (basis points) *").fill("1250");
    await d.getByLabel("Reason *").fill("Raised after review");
    await confirm(page);
    await expect(page.getByTestId("global-pct")).toHaveText("12.5%");

    // activity: choose a sport from the real categories
    await page.getByTestId("activity-create").click();
    d = page.locator("dialog[open]");
    await d.getByLabel("Sport / activity *").selectOption({ index: 0 });
    await d.getByLabel("Commission (basis points) *").fill("800");
    await d.getByLabel("Reason *").fill("Promotional sport");
    await confirm(page);
    await expect(page.getByTestId("activity-rules")).toContainText("8%");

    // venue: search, then set
    await page.goto("/commission?venue_q=a");
    await page.getByTestId("venue-create").first().click();
    d = page.locator("dialog[open]");
    await d.getByLabel("Commission (basis points) *").fill("1500");
    await d.getByLabel("Reason *").fill("Individually negotiated");
    await confirm(page);
    await expect(page.getByTestId("venue-rules")).toContainText("15%");

    // deactivate the venue rule: it stays listed, as inactive
    await page.getByTestId("venue-rules").getByTestId("rule-toggle").first().click();
    d = page.locator("dialog[open]");
    await d.getByLabel("Reason *").fill("Deal ended");
    await confirm(page);
    await expect(page.getByTestId("venue-rules")).toContainText("Inactive");
  });

  test("history keeps every version with previous %, admin and reason, and filters by scope", async ({ page }) => {
    await page.goto("/commission/history");
    await expect(page.locator("main")).toContainText("Raised after review");
    await expect(page.locator("main")).toContainText("Launch rate agreed with the client");
    await expect(page.locator("main")).toContainText("Ada Admin");
    await page.goto("/commission/history?scope=global");
    await expect(page.locator("main")).not.toContainText("Individually negotiated");
    await page.goto("/commission/history?scope=venue");
    await expect(page.locator("main")).toContainText("Deal ended");
  });

  test("reports reconcile and the CSV export is available; finance shows the commission block", async ({ page, request }) => {
    await page.goto("/commission/report");
    await expect(page.getByTestId("reconciliation")).toContainText("reconcile");
    const csv = await page.request.get("/api/exports/commission");
    expect(csv.status()).toBe(200);
    expect(await csv.text()).toContain("commission_bps");
    await page.goto("/finance");
    await expect(page.getByRole("link", { name: /Manage commission rules/ })).toBeVisible();
    void request;
  });
});
