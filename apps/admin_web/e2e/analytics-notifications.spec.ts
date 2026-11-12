import { expect, test } from "@playwright/test";
import { adminToken, api } from "./support/helpers";

type BA = { total: number; series: { total: number }[]; status_distribution: { status: string; count: number }[] };
type RA = { captured_count: number; failed_count: number; success_rate_percent: number | null; series: { captured_paise: number }[] };

test.describe("analytics", () => {
  test("bookings tab: totals equal the API aggregate, charts render, granularity switches", async ({ page, request }) => {
    const t = await adminToken(request);
    const a = await api<BA>(request, `/admin/analytics/bookings?granularity=day`, t);
    await page.goto("/analytics");
    await expect(page.getByTestId("stat-card").filter({ has: page.getByText("Total bookings", { exact: true }) }).getByTestId("stat-value")).toHaveText(String(a.total));
    expect(a.series.reduce((s, b) => s + b.total, 0)).toBe(a.total);
    await expect(page.getByTestId("chart")).toHaveCount(2);
    await expect(page.locator("svg.recharts-surface").first()).toBeVisible();
    for (const g of ["Weekly", "Monthly", "Daily"]) {
      await page.getByRole("link", { name: g }).click();
      await expect(page.getByRole("link", { name: g })).toHaveAttribute("aria-current", "true");
      await expect(page.getByTestId("chart").first()).toBeVisible();
    }
    const week = await api<BA>(request, `/admin/analytics/bookings?granularity=week`, t);
    expect(week.total).toBe(a.total);
    const dist = Object.fromEntries(a.status_distribution.map((s) => [s.status, s.count]));
    expect(dist.confirmed).toBe(30);
    expect(dist.pending_payment).toBe(1);
  });

  test("transactions tab: success rate and amounts come from recorded payments; platform revenue stays unavailable", async ({ page, request }) => {
    const r = await api<RA>(request, "/admin/analytics/revenue", await adminToken(request));
    await page.goto("/analytics?tab=revenue");
    const stat = (l: string) => page.getByTestId("stat-card").filter({ has: page.getByText(l, { exact: true }) }).getByTestId("stat-value");
    await expect(stat("Successful")).toHaveText(String(r.captured_count));
    await expect(stat("Failed")).toHaveText(String(r.failed_count));
    await expect(stat("Success rate")).toHaveText(`${r.success_rate_percent}%`);
    expect(r.success_rate_percent).toBeCloseTo((30 * 100) / 31, 1);
    await expect(page.getByTestId("money-platform-revenue")).toHaveText("Not available");
    await expect(page.getByTestId("money-owner-earnings")).toHaveText("Not available");
    await expect(page.getByTestId("money-refunds")).toHaveText("Not available");
  });

  test("platform tab: registrations, venue growth, categories, top venues", async ({ page }) => {
    await page.goto("/analytics?tab=platform");
    await expect(page.getByTestId("chart")).toHaveCount(4);
    await expect(page.getByRole("heading", { name: "Popular categories" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Most-booked venues" })).toBeVisible();
    await expect(page.getByTestId("stat-card").filter({ has: page.getByText("New customers", { exact: true }) }).getByTestId("stat-value")).toHaveText("6");
  });

  test("an empty period shows empty charts; an invalid period shows an error state, not a crash", async ({ page }) => {
    await page.goto("/analytics?from=2020-01-01&to=2020-01-31");
    await expect(page.getByTestId("chart-empty").first()).toBeVisible();
    await expect(page.getByTestId("error-state")).toHaveCount(0);
    await page.goto("/analytics?from=2010-01-01&to=2026-01-01");
    await expect(page.getByTestId("error-state")).toContainText("at most 366 days");
  });
});

test.describe("notifications", () => {
  test("lists platform events with unread state; the bell count matches", async ({ page, request }) => {
    const t = await adminToken(request);
    const list = await api<{ items: { type: string; is_read: boolean }[] }>(request, "/notifications", t);
    const unread = list.items.filter((n) => !n.is_read).length;
    expect(list.items.map((n) => n.type)).toEqual(expect.arrayContaining(["admin.new_customer", "admin.new_owner"]));
    await page.goto("/notifications");
    await expect(page.getByTestId("notification").first()).toBeVisible();
    await expect(page.getByTestId("bell-count")).toHaveText(String(unread));
    await expect(page.getByText("New customer registered")).toBeVisible();
    await expect(page.getByText("New owner registered")).toBeVisible();
    await expect(page.locator('[data-testid=notification][data-read="false"]')).toHaveCount(unread);
  });

  test("mark one read, then mark all read", async ({ page }) => {
    await page.goto("/notifications");
    const before = await page.locator('[data-testid=notification][data-read="false"]').count();
    expect(before).toBeGreaterThan(0);
    await page.getByRole("button", { name: "Mark read" }).first().click();
    await expect(page.locator('[data-testid=notification][data-read="false"]')).toHaveCount(before - 1);
    await page.getByTestId("mark-all").click();
    await expect(page.locator('[data-testid=notification][data-read="false"]')).toHaveCount(0);
    await expect(page.getByTestId("bell-count")).toHaveCount(0);
    await page.getByLabel("Show").selectOption("unread");
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(page.getByText("You are all caught up")).toBeVisible();
  });
});
