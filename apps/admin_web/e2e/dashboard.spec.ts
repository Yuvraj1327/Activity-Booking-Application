import { expect, test } from "@playwright/test";
import { adminToken, api } from "./support/helpers";

type D = { totals: Record<string, number>; period: { bookings: number; confirmed: number; completed: number; failed_payments: number; pending: number; cancelled: number; transactions: number; money: { successful_payment_paise: number } } };

test.describe("dashboard", () => {
  test("every KPI equals the value the API returns for the same range", async ({ page, request }) => {
    await page.goto("/dashboard");
    const t = await adminToken(request);
    const d = await api<D>(request, "/admin/dashboard", t);
    const stat = (label: string) => page.getByTestId("stat-card").filter({ has: page.getByText(label, { exact: true }) }).getByTestId("stat-value");
    // active users are counted by their real account status; completed is never merged into confirmed
    await expect(stat("Active customers")).toHaveText(String(d.totals.active_customers));
    await expect(stat("Active venue owners")).toHaveText(String(d.totals.active_owners));
    await expect(stat("Pending venue approvals")).toHaveText(String(d.totals.pending_venue_approvals));
    await expect(stat("Venues")).toHaveText(String(d.totals.venues));
    await expect(stat("Bookings created")).toHaveText(String(d.period.bookings));
    await expect(stat("Confirmed (upcoming)")).toHaveText(String(d.period.confirmed));
    await expect(stat("Completed")).toHaveText(String(d.period.completed));
    await expect(stat("Cancelled")).toHaveText(String(d.period.cancelled));
    await expect(stat("Failed payments")).toHaveText(String(d.period.failed_payments));
    // independent check against the seed: 6 customers, 4 owners, 4 venues, 30 paid bookings
    expect(d.totals.customers).toBe(6);
    expect(d.totals.owners).toBe(4);
    expect(d.totals.venues).toBe(4);
    expect(d.period.confirmed).toBe(30);
  });

  test("charts, recent bookings, registrations, popular venues and activity render from real data", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByTestId("chart")).toHaveCount(2);
    await expect(page.locator("svg.recharts-surface").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Recent bookings" })).toBeVisible();
    await expect(page.locator("table tbody tr")).toHaveCount(5);
    await expect(page.getByRole("heading", { name: "Popular venues" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Recent registrations" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Platform activity" })).toBeVisible();
    await expect(page.getByText("Zoya Khan")).toBeVisible();
  });

  test("money is split into five defined figures and unapproved ones say so", async ({ page, request }) => {
    await page.goto("/dashboard");
    const d = await api<D>(request, "/admin/dashboard", await adminToken(request));
    const panel = page.getByTestId("money-panel");
    await expect(panel.getByText("Gross booking value")).toBeVisible();
    await expect(panel.getByText("Successful payments")).toBeVisible();
    await expect(panel.getByTestId("money-platform-revenue")).toHaveText("Not available");
    await expect(panel.getByTestId("money-owner-earnings")).toHaveText("Not available");
    await expect(panel.getByTestId("money-tax-collected")).toHaveText("Not available");
    // refunds are real recorded data (zero here), not an unavailable rule
    await expect(panel.getByTestId("money-refunds")).toContainText("₹");
    const paid = (await panel.getByTestId("money-paid").innerText()).replace(/[^\d.]/g, "");
    expect(Number(paid)).toBeCloseTo(d.period.money.successful_payment_paise / 100, 2);
  });

  test("date presets change the URL and the data; today shows only today's bookings", async ({ page, request }) => {
    const t = await adminToken(request);
    await page.goto("/dashboard");
    await expect(page.getByRole("link", { name: "Last 30 days" })).toHaveAttribute("aria-current", "true");
    await page.getByRole("link", { name: "Today" }).click();
    await expect(page).toHaveURL(/range=today/);
    await expect(page.getByRole("link", { name: "Today" })).toHaveAttribute("aria-current", "true");
    const today = new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
    const d = await api<D>(request, `/admin/dashboard?from=${today}&to=${today}`, t);
    await expect(page.getByTestId("stat-card").filter({ has: page.getByText("Bookings created", { exact: true }) }).getByTestId("stat-value")).toHaveText(String(d.period.bookings));
    for (const label of ["Last 7 days", "This month", "Last 30 days"]) {
      await page.getByRole("link", { name: label }).click();
      await expect(page.getByRole("link", { name: label })).toHaveAttribute("aria-current", "true");
    }
  });

  test("custom range: a window with no data shows zeroes and empty states, not errors", async ({ page }) => {
    await page.goto("/dashboard?from=2020-01-01&to=2020-01-31");
    await expect(page.getByTestId("stat-card").filter({ has: page.getByText("Bookings created", { exact: true }) }).getByTestId("stat-value")).toHaveText("0");
    await expect(page.getByTestId("chart-empty").first()).toBeVisible();
    await expect(page.getByTestId("error-state")).toHaveCount(0);
    await expect(page.getByText("No bookings in this period")).toBeVisible();
  });

  test("custom range form submits dates", async ({ page }) => {
    await page.goto("/dashboard");
    await page.getByLabel("From").fill("2020-02-01");
    await page.getByLabel("To", { exact: true }).fill("2020-02-10");
    await page.getByRole("button", { name: "Custom range" }).click();
    await expect(page).toHaveURL(/from=2020-02-01&to=2020-02-10/);
    await expect(page.getByText(/1 Feb 2020 – 10 Feb 2020/)).toBeVisible();
  });
});
