import { test } from "@playwright/test";
import { adminToken, api, ADMIN, signIn, users } from "./support/helpers";
import { mkdirSync } from "node:fs";

// Captures the documentation screenshots from the real stack. Run on its own for a fresh seed:
//   npx playwright test e2e/screenshots.spec.ts --project=setup --project=desktop --project=tablet
const DIR = "../../docs/screenshots";
mkdirSync(DIR, { recursive: true });

test("capture", async ({ page, request, browser }, info) => {
  test.skip(info.project.name !== "desktop", "tablet shots are taken in the second test");
  const t = await adminToken(request);
  const shot = async (name: string, path: string, opts: { full?: boolean } = {}) => {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500); // chart animation
    await page.screenshot({ path: `${DIR}/${name}.png`, fullPage: opts.full ?? true });
  };
  await shot("01-dashboard", "/dashboard");
  await shot("02-analytics-bookings", "/analytics");
  await shot("03-analytics-transactions", "/analytics?tab=revenue");
  await shot("04-analytics-platform", "/analytics?tab=platform");
  await shot("05-owners", "/owners");
  await shot("06-owner-detail", `/owners/${users()["priya@example.com"].id}`);
  await shot("07-customers", "/customers");
  await shot("08-customer-detail", `/customers/${users()["aarav@example.com"].id}`);
  await shot("09-venues", "/venues");
  const v = (await api<{ items: { id: string }[] }>(request, "/admin/venues?q=smash", t)).items[0];
  await shot("10-venue-detail", `/venues/${v.id}`);
  await shot("11-bookings", "/bookings");
  const b = (await api<{ items: { id: string }[] }>(request, "/admin/bookings?status=confirmed&limit=1", t)).items[0];
  await shot("12-booking-detail", `/bookings/${b.id}`);
  await shot("13-payments", "/payments");
  const p = (await api<{ items: { id: string }[] }>(request, "/admin/payments?status=captured&limit=1", t)).items[0];
  await shot("14-payment-detail", `/payments/${p.id}`);
  await shot("15-notifications", "/notifications");
  // suspension dialog
  await page.goto(`/customers/${users()["isha@example.com"].id}`);
  await page.getByTestId("status-open").click();
  await page.getByLabel("Reason").fill("Example: repeated no-shows reported by owners");
  await page.screenshot({ path: `${DIR}/16-suspend-dialog.png` });
  await page.keyboard.press("Escape");
  await shot("17-audit-log", "/audit");
  await shot("18-empty-period", "/dashboard?from=2020-01-01&to=2020-01-31");

  // signed-out screens
  const anon = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const ap = await anon.newPage();
  await ap.goto("http://127.0.0.1:3100/login");
  await ap.screenshot({ path: `${DIR}/19-login.png` });
  await signIn(ap, "aarav@example.com", "E2E-user-pass");
  await ap.waitForURL(/unauthorized/);
  await ap.screenshot({ path: `${DIR}/20-access-denied.png` });
  await anon.close();
  void ADMIN;
});

test("tablet", async ({ page }, info) => {
  test.skip(info.project.name !== "tablet", "tablet viewport only");
  for (const [name, path] of [["21-tablet-dashboard", "/dashboard"], ["22-tablet-bookings", "/bookings"]] as const) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${DIR}/${name}.png`, fullPage: true });
  }
});
