import { expect, test } from "@playwright/test";
import { ADMIN, adminToken, api, tokenFor, USER_PASSWORD, users } from "./support/helpers";

const rows = (page: import("@playwright/test").Page) => page.locator("tbody tr");

test.describe("owners", () => {
  test("lists owners with counts, masks phone, and links to detail", async ({ page }) => {
    await page.goto("/owners");
    await expect(page.getByRole("heading", { name: "Venue owners" })).toBeVisible();
    await expect(rows(page)).toHaveCount(4);
    const priya = rows(page).filter({ hasText: "Priya Sharma" });
    await expect(priya).toContainText("Smash Arena Pvt Ltd");
    await expect(priya).toContainText("1/1");
    await expect(priya).toContainText("0001");
    await expect(priya).not.toContainText("+91980000");
  });

  test("search, status filter, sort and clear all work through the URL", async ({ page }) => {
    await page.goto("/owners");
    await page.getByRole("searchbox").or(page.getByPlaceholder("Search name, e-mail or business")).fill("greenfield");
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(page).toHaveURL(/q=greenfield/);
    await expect(rows(page)).toHaveCount(1);
    await expect(rows(page).first()).toContainText("Rahul Verma");
    await page.getByRole("link", { name: "Clear" }).click();
    await expect(rows(page)).toHaveCount(4);
    await page.getByLabel("Account status").selectOption("suspended");
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(page.getByTestId("empty-state")).toBeVisible();
    await page.goto("/owners?sort=name&order=asc");
    await expect(rows(page).first()).toContainText("Arjun Rao");
    await page.goto("/owners?q=%25");
    await expect(page.getByTestId("empty-state")).toBeVisible();
  });

  test("owner detail shows contact, KYC, venues, paginated booking history and account history", async ({ page }) => {
    const id = users()["priya@example.com"].id;
    await page.goto(`/owners/${id}`);
    await expect(page.getByRole("heading", { name: "Priya Sharma" })).toBeVisible();
    await expect(page.getByText("priya@example.com").first()).toBeVisible();
    await expect(page.getByText("12 MG Road, Bengaluru")).toBeVisible();
    await expect(page.getByRole("link", { name: "Smash Arena Koramangala" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Booking history at this owner's venues" })).toBeVisible();
    await expect(page.getByTestId("kyc-panel")).toBeVisible();
    await expect(page.getByTestId("payout-history")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Account action history" })).toBeVisible();
    // an owner's content is not editable by admins
    await expect(page.getByRole("button", { name: /edit|delete|publish|remove/i })).toHaveCount(0);
  });

  test("unknown owner id gives the not-found page; a customer id is not an owner", async ({ page }) => {
    await page.goto("/owners/00000000-0000-0000-0000-000000000000");
    await expect(page.getByText(/could not be found|not found/i).first()).toBeVisible();
    await page.goto(`/owners/${users()["aarav@example.com"].id}`);
    await expect(page.getByText(/could not be found|not found/i).first()).toBeVisible();
  });

  test("suspend then reactivate an owner: reason is required, the API enforces it, the audit log records both", async ({ page, request }) => {
    const rahul = users()["rahul@example.com"].id;
    await page.goto(`/owners/${rahul}`);
    await page.getByTestId("status-open").click();
    // browser-level validation: a reason is required
    await page.getByTestId("status-confirm").click();
    await expect(page.getByTestId("status-result")).toHaveCount(0);
    await page.locator("dialog[open]").getByLabel("Reason").fill("Repeated policy complaints");
    await page.getByTestId("status-confirm").click();
    await expect(page.getByTestId("status-result")).toContainText("recorded in the audit log");
    await page.getByRole("button", { name: "Close" }).click();
    await expect(page.getByText("Suspended").first()).toBeVisible();

    // the owner is now refused by the backend
    const ownerToken = await tokenFor(request, "rahul@example.com", USER_PASSWORD);
    const blocked = await request.get("http://127.0.0.1:8018/api/v1/owners/dashboard", { headers: { Authorization: `Bearer ${ownerToken}` } });
    expect(blocked.status()).toBe(403);
    expect((await blocked.json()).code).toBe("ACCOUNT_SUSPENDED");

    await page.goto("/audit?action=admin.account_status_changed");
    await expect(rows(page).first()).toContainText("admin.account_status_changed");
    await expect(rows(page).first()).toContainText("Repeated policy complaints");
    await expect(rows(page).first()).toContainText("active → suspended");

    // reactivate
    await page.goto(`/owners/${rahul}`);
    await page.getByTestId("status-open").click();
    await page.locator("dialog[open]").getByLabel("Reason").fill("Cleared after review");
    await page.getByTestId("status-confirm").click();
    await expect(page.getByTestId("status-result")).toContainText("audit log");
    const ok = await request.get("http://127.0.0.1:8018/api/v1/owners/dashboard", { headers: { Authorization: `Bearer ${ownerToken}` } });
    expect(ok.status()).toBe(200);
    const audit = await api<{ items: { metadata: Record<string, string>; actor_role: string }[] }>(request, "/admin/audit-logs?action=admin.account_status_changed", await adminToken(request));
    expect(audit.items.map((a) => a.metadata.to).slice(0, 2)).toEqual(["active", "suspended"]);
    expect(audit.items.every((a) => a.actor_role === "admin")).toBeTruthy();
  });
});

test.describe("customers", () => {
  test("lists, searches, filters by status, shows history", async ({ page }) => {
    await page.goto("/customers");
    await expect(rows(page)).toHaveCount(6);
    await page.getByLabel("Account status").selectOption("suspended");
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(rows(page)).toHaveCount(1);
    await expect(rows(page).first()).toContainText("Neel Joshi");
    await page.goto("/customers?q=aarav");
    await expect(rows(page)).toHaveCount(1);
    await rows(page).first().getByRole("link", { name: "Aarav Mehta" }).click();
    await expect(page.getByRole("heading", { name: "Aarav Mehta" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Booking history" })).toBeVisible();
    await expect(page.locator("tbody tr").first()).toContainText("ZUR-");
  });

  test("suspend and reactivate a customer through the same audited path", async ({ page, request }) => {
    const diya = users()["diya@example.com"].id;
    await page.goto(`/customers/${diya}`);
    await page.getByTestId("status-open").click();
    await page.getByLabel("Reason").fill("Chargeback abuse");
    await page.getByTestId("status-confirm").click();
    await expect(page.getByTestId("status-result")).toContainText("audit log");
    const t = await tokenFor(request, "diya@example.com", USER_PASSWORD);
    expect((await request.get("http://127.0.0.1:8018/api/v1/bookings", { headers: { Authorization: `Bearer ${t}` } })).status()).toBe(403);
    await page.reload();
    await page.getByTestId("status-open").click();
    await page.getByLabel("Reason").fill("Resolved");
    await page.getByTestId("status-confirm").click();
    await expect(page.getByTestId("status-result")).toContainText("audit log");
    expect((await request.get("http://127.0.0.1:8018/api/v1/bookings", { headers: { Authorization: `Bearer ${t}` } })).status()).toBe(200);
  });

  test("admin accounts cannot be suspended through the API, not even their own", async ({ request }) => {
    const t = await adminToken(request);
    const r = await request.patch(`http://127.0.0.1:8018/api/v1/admin/customers/${users()[ADMIN.email].id}/status`, { headers: { Authorization: `Bearer ${t}` }, data: { status: "suspended", reason: "self" } });
    expect(r.status()).toBe(403);
    expect((await r.json()).code).toBe("ADMIN_ACCOUNT_PROTECTED");
  });
});

test.describe("venue monitoring", () => {
  test("lists all venues read-only with owner, categories, location, publication, bookings", async ({ page }) => {
    await page.goto("/venues");
    await expect(rows(page)).toHaveCount(4);
    const smash = rows(page).filter({ hasText: "Smash Arena Koramangala" });
    await expect(smash).toContainText("Badminton");
    await expect(smash).toContainText("Bengaluru");
    await expect(smash).toContainText("Priya Sharma");
    await expect(page.getByRole("button", { name: /edit|delete|publish/i })).toHaveCount(0);
    await page.locator("select[name=status]").selectOption("draft");
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(rows(page)).toHaveCount(1);
    await expect(rows(page).first()).toContainText("Blue Lagoon Annex");
  });

  test("venue detail shows moderation actions and links to the venue's bookings", async ({ page }) => {
    await page.goto("/venues?q=greenfield");
    await page.getByRole("link", { name: "Greenfield Turf" }).click();
    await expect(page.getByText("Owners edit their own listings.")).toBeVisible();
    await expect(page.getByTestId("moderation-actions")).toBeVisible();
    await page.getByRole("link", { name: "View bookings" }).click();
    await expect(page).toHaveURL(/venue_id=/);
    await expect(page.locator("select[name=venue_id]")).not.toHaveValue("");
    for (const r of await rows(page).all()) await expect(r).toContainText("Greenfield Turf");
  });
});
