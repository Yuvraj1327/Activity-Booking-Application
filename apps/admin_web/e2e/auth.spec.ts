import { expect, test } from "@playwright/test";
import { ADMIN, API, adminToken, signIn, tokenFor, USER_PASSWORD, users } from "./support/helpers";

test.use({ storageState: { cookies: [], origins: [] } });

test.describe("admin authentication and authorisation", () => {
  for (const path of ["/dashboard", "/owners", "/customers", "/venues", "/bookings", "/payments", "/analytics", "/notifications", "/audit", "/owners/00000000-0000-0000-0000-000000000000"]) {
    test(`signed-out visitor to ${path} is sent to /login`, async ({ page }) => {
      await page.goto(path);
      await expect(page).toHaveURL(/\/login$/);
    });
  }

  test("signed-out CSV export is refused", async ({ request }) => {
    const r = await request.get("/api/exports/bookings", { maxRedirects: 0 });
    expect([302, 307, 308, 401, 403]).toContain(r.status());
  });

  test("wrong password shows one generic error and stays on /login", async ({ page }) => {
    await signIn(page, ADMIN.email, "not-the-password");
    await expect(page.getByText("Incorrect e-mail or password.")).toBeVisible();
    await expect(page.locator("form [role=alert]")).toHaveCount(1);
    await expect(page).toHaveURL(/\/login$/);
  });

  test("unknown e-mail gets the same message", async ({ page }) => {
    await signIn(page, "nobody@example.com", "whatever");
    await expect(page.getByText("Incorrect e-mail or password.")).toBeVisible();
    await expect(page.locator("form [role=alert]")).toHaveCount(1);
  });

  test("a customer who signs in successfully is still refused by the API-backed role check", async ({ page }) => {
    await signIn(page, "aarav@example.com", USER_PASSWORD);
    await expect(page).toHaveURL(/\/unauthorized$/);
    await expect(page.getByRole("heading", { name: "Access denied" })).toBeVisible();
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/unauthorized$/);
    await page.goto("/owners");
    await expect(page).toHaveURL(/\/unauthorized$/);
  });

  test("an owner is refused too", async ({ page }) => {
    await signIn(page, "priya@example.com", USER_PASSWORD);
    await expect(page).toHaveURL(/\/unauthorized$/);
  });

  test("the admin signs in, sees the console, and signing out ends the session", async ({ page }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login$/);
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login$/);
  });

  test("the API itself rejects anonymous, customer and owner tokens (frontend protection is not relied on)", async ({ request }) => {
    for (const path of ["/admin/dashboard", "/admin/owners", "/admin/bookings", "/admin/payments", "/admin/exports/bookings.csv"]) {
      expect((await request.get(`${API}${path}`)).status()).toBe(401);
      const cust = await tokenFor(request, "aarav@example.com", USER_PASSWORD);
      expect((await request.get(`${API}${path}`, { headers: { Authorization: `Bearer ${cust}` } })).status()).toBe(403);
      const owner = await tokenFor(request, "priya@example.com", USER_PASSWORD);
      expect((await request.get(`${API}${path}`, { headers: { Authorization: `Bearer ${owner}` } })).status()).toBe(403);
    }
    const t = await adminToken(request);
    expect((await request.get(`${API}/admin/dashboard`, { headers: { Authorization: `Bearer ${t}` } })).status()).toBe(200);
  });

  test("a user cannot give themselves the admin role", async ({ request }) => {
    const cust = await tokenFor(request, "aarav@example.com", USER_PASSWORD);
    const h = { Authorization: `Bearer ${cust}` };
    const r = await request.patch(`${API}/profiles/me`, { headers: h, data: { role: "admin" } });
    expect([405, 422]).toContain(r.status());
    expect((await request.get(`${API}/admin/me`, { headers: h })).status()).toBe(403);
    const reg = await request.post(`${API}/auth/profile`, { headers: h, data: { role: "admin", full_name: "x" } });
    expect(reg.status()).toBe(422);
    void users;
  });

  test("a suspended account is refused on its next request", async ({ request }) => {
    const neel = await tokenFor(request, "neel@example.com", USER_PASSWORD);
    const r = await request.get(`${API}/auth/me`, { headers: { Authorization: `Bearer ${neel}` } });
    expect(r.status()).toBeLessThan(500);
    const b = await request.get(`${API}/bookings`, { headers: { Authorization: `Bearer ${neel}` } });
    expect(b.status()).toBe(403);
    expect((await b.json()).code).toBe("ACCOUNT_SUSPENDED");
  });
});
