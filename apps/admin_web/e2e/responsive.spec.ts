import { expect, test } from "@playwright/test";
import { adminToken, api, users } from "./support/helpers";

const PAGES = ["/dashboard", "/analytics", "/analytics?tab=revenue", "/analytics?tab=platform", "/owners", "/customers", "/venues", "/bookings", "/payments", "/notifications", "/audit"];

test.describe("responsive layout", () => {
  for (const path of PAGES) {
    test(`${path} has no page-level horizontal scroll`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      const { sw, cw } = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
      expect(sw, `${path}: scrollWidth ${sw} > clientWidth ${cw}`).toBeLessThanOrEqual(cw);
    });
  }

  test("detail pages fit too", async ({ page, request }) => {
    const t = await adminToken(request);
    const b = (await api<{ items: { id: string }[] }>(request, "/admin/bookings?limit=1", t)).items[0];
    const p = (await api<{ items: { id: string }[] }>(request, "/admin/payments?limit=1", t)).items[0];
    for (const path of [`/bookings/${b.id}`, `/payments/${p.id}`, `/owners/${users()["priya@example.com"].id}`]) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      const { sw, cw } = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
      expect(sw, path).toBeLessThanOrEqual(cw);
    }
  });

  test("navigation adapts: labelled sidebar on desktop, icon rail on tablet", async ({ page }, info) => {
    await page.goto("/dashboard");
    const nav = page.getByRole("navigation", { name: "Main", exact: true });
    await expect(nav).toBeVisible();
    const width = (await page.locator("aside").boundingBox())!.width;
    if (info.project.name === "tablet") {
      expect(width).toBeLessThan(100);
      await expect(page.locator("aside").getByText("Dashboard", { exact: true }).first()).toBeHidden();
      await expect(nav.getByRole("link", { name: "Bookings" })).toBeVisible(); // still reachable by accessible name
    } else {
      expect(width).toBeGreaterThan(200);
      await expect(nav.locator("span.lg\\:inline", { hasText: "Bookings" })).toBeVisible();
    }
    await nav.getByRole("link", { name: "Bookings" }).click();
    await expect(page).toHaveURL(/\/bookings$/);
  });

  test("wide tables scroll inside their card instead of breaking the page", async ({ page }) => {
    await page.goto("/bookings");
    const wrapper = page.locator("table").first().locator("xpath=..");
    await expect(wrapper).toHaveCSS("overflow-x", "auto");
  });
});

test.describe("loading and error states", () => {
  test("an API failure on a list shows an inline error, the shell stays usable", async ({ page }) => {
    await page.goto("/analytics?from=2010-01-01&to=2026-01-01");
    await expect(page.getByTestId("error-state")).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Main", exact: true })).toBeVisible();
  });

  test("a missing record gives a not-found page", async ({ page }) => {
    await page.goto("/bookings/00000000-0000-0000-0000-000000000000");
    await expect(page.getByText(/not found|could not be found/i).first()).toBeVisible();
    await page.goto("/bookings/not-a-uuid");
    await expect(page.getByText(/not found|could not be found/i).first()).toBeVisible();
  });
});
