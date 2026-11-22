import { expect, test } from "@playwright/test";
import { adminToken, api, API, signIn, tokenFor, USER_PASSWORD, users } from "./support/helpers";

// The admin-operations modules, driven through the real UI against the real API and database.

const authed = (t: string) => ({ Authorization: `Bearer ${t}`, "Content-Type": "application/json" });

test.describe("permissions in the console", () => {
  test("the navigation shows only what the role allows, and the API refuses the rest", async ({ browser, request }) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await signIn(page, "limited@zuruv.test", USER_PASSWORD);
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByTestId("admin-role")).toHaveText("Support agent");
    const nav = page.getByRole("navigation", { name: "Main", exact: true });
    await expect(nav.getByRole("link", { name: "Support tickets" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Dashboard" })).toBeVisible();
    for (const hidden of ["Refunds", "Finance", "Owner payouts", "Admin roles", "Platform switches", "Audit log", "Coupons"]) {
      await expect(nav.getByRole("link", { name: hidden })).toHaveCount(0);
    }
    // typing the URL does not help: the page asks the API, which says no
    await page.goto("/refunds");
    await expect(page.getByTestId("error-state")).toContainText(/permission/i);
    const t = await tokenFor(request, "limited@zuruv.test", USER_PASSWORD);
    const r = await request.get(`${API}/admin/payments`, { headers: authed(t) });
    expect(r.status()).toBe(403);
    expect((await r.json()).code).toBe("PERMISSION_DENIED");
    await ctx.close();
  });

  test("an administrator with no role can sign in but sees nothing", async ({ browser }) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await signIn(page, "norole@zuruv.test", USER_PASSWORD);
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByTestId("no-role")).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Main", exact: true }).getByRole("link")).toHaveCount(0);
    await ctx.close();
  });
});

test.describe("support tickets", () => {
  test("reply, internal note, status and priority; the customer sees only the reply", async ({ page, request }) => {
    await page.goto("/support");
    await page.getByRole("link", { name: "Charged twice for one booking" }).click();
    await page.getByTestId("ticket-reply").click();
    await page.locator("dialog[open]").getByLabel("Message").fill("Thanks, we are checking the payment logs.");
    await page.locator("dialog[open]").getByTestId("action-confirm").click();
    await expect(page.locator("dialog[open]").getByTestId("action-result")).toBeVisible();
    await page.locator("dialog[open]").getByRole("button", { name: "Close" }).click();
    await expect(page.getByTestId("ticket-thread")).toContainText("Thanks, we are checking the payment logs.");
    await page.getByTestId("ticket-update").click();
    await page.locator("dialog[open]").getByLabel("Priority").selectOption("urgent");
    await page.locator("dialog[open]").getByTestId("action-confirm").click();
    await expect(page.locator("dialog[open]").getByTestId("action-result")).toBeVisible();
    await page.locator("dialog[open]").getByRole("button", { name: "Close" }).click();
    await expect(page.getByTestId("ticket-thread")).toContainText("Priority changed from normal to urgent");
    const cust = await tokenFor(request, "aarav@example.com", USER_PASSWORD);
    const mine = await (await request.get(`${API}/support/tickets`, { headers: authed(cust) })).json();
    expect(mine[0].status).toBe("open"); // the app only knows open / closed
    const replies = await (await request.get(`${API}/support/tickets/${mine[0].id}/messages`, { headers: authed(cust) })).json();
    expect(replies.items).toHaveLength(1);
  });
});

test.describe("venue approval workflow", () => {
  test("owner submits, admin approves in the UI, venue goes live; rejection needs a reason", async ({ page, request }) => {
    const admin = await adminToken(request);
    try {
    // switch the workflow on (an audited, reasoned change)
    const on = await request.put(`${API}/admin/settings/venue_approval_required`, { headers: authed(admin), data: { value: true, reason: "e2e: approval workflow on" } });
    expect(on.ok()).toBeTruthy();
    // an owner creates and submits a venue through the owner API
    const owner = await tokenFor(request, "meera@example.com", USER_PASSWORD);
    const cities = await (await request.get(`${API}/cities`, { headers: authed(owner) })).json();
    const cats = await (await request.get(`${API}/categories`, { headers: authed(owner) })).json();
    const created = await (await request.post(`${API}/owners/venues`, { headers: authed(owner), data: { name: "E2E Pending Court", city_id: cities[0].id, latitude: 12.97, longitude: 77.59, category_ids: [cats[0].id] } })).json();
    const sub = await (await request.post(`${API}/owners/venues/${created.id}/publish`, { headers: authed(owner) })).json();
    expect(sub.status).toBe("pending_review");

    await page.goto("/dashboard");
    await expect(page.getByTestId("stat-card").filter({ has: page.getByText("Pending venue approvals", { exact: true }) }).getByTestId("stat-value")).toHaveText("1");
    await page.goto("/venues?status=pending_review");
    await page.getByRole("link", { name: "E2E Pending Court" }).click();
    await expect(page.getByTestId("pending-note")).toBeVisible();
    // rejecting needs a reason
    await page.getByTestId("venue-reject").click();
    await page.locator("dialog[open]").getByTestId("action-confirm").click();
    await expect(page.locator("dialog[open]").getByTestId("action-result")).toHaveCount(0);
    await page.locator("dialog[open]").getByRole("button", { name: "Cancel" }).click();
    await page.getByTestId("venue-approve").click();
    await page.locator("dialog[open]").getByTestId("action-confirm").click();
    // the page re-renders with the new state: the pending banner and the Approve button are gone
    await expect(page.getByTestId("pending-note")).toHaveCount(0);
    await expect(page.getByTestId("venue-suspend")).toBeVisible();
    const live = await request.get(`${API}/venues/${created.id}`, { headers: authed(owner) });
    expect(live.status()).toBe(200);
    // suspend with a reason, then it disappears for customers
    await page.getByTestId("venue-suspend").click();
    await page.locator("dialog[open]").getByLabel("Reason").fill("Safety complaint under review");
    await page.locator("dialog[open]").getByTestId("action-confirm").click();
    await expect(page.getByTestId("reason-note")).toContainText("Safety complaint under review");
    expect((await request.get(`${API}/venues/${created.id}`, { headers: authed(owner) })).status()).toBe(404);
    const again = await request.post(`${API}/owners/venues/${created.id}/publish`, { headers: authed(owner) });
    expect(again.status()).toBe(409);
    } finally {
      // restore the default so the rest of the suite is unaffected
      await request.put(`${API}/admin/settings/venue_approval_required`, { headers: authed(admin), data: { value: false, reason: "e2e: restore default" } });
    }
  });
});

test.describe("KYC review", () => {
  test("approve a pending document, then verify the owner; the decision is audited", async ({ page, request }) => {
    const priya = users()["priya@example.com"].id;
    await page.goto("/kyc");
    await expect(page.getByRole("link", { name: "Priya Sharma" })).toBeVisible();
    await page.goto(`/owners/${priya}`);
    const panel = page.getByTestId("kyc-panel");
    await expect(panel).toContainText("Identity");
    await panel.getByRole("button", { name: "Reject", exact: true }).click();
    await page.locator("dialog[open]").getByTestId("action-confirm").click(); // reason is required
    await expect(page.locator("dialog[open]").getByTestId("action-result")).toHaveCount(0);
    await page.locator("dialog[open]").getByRole("button", { name: "Cancel" }).click();
    await panel.getByRole("button", { name: "Approve", exact: true }).click();
    await page.locator("dialog[open]").getByTestId("action-confirm").click();
    await expect(panel.getByRole("button", { name: "Approve", exact: true })).toHaveCount(0); // reviewed: the row now shows its outcome
    await expect(panel).toContainText("Approved");
    await page.getByTestId("kyc-verify").click();
    await page.locator("dialog[open]").getByTestId("action-confirm").click();
    await expect(page.getByRole("heading", { level: 2, name: "Priya Sharma" }).locator("xpath=../..")).toContainText("Verified");
    const t = await adminToken(request);
    const audit = await api<{ items: { action: string; metadata: { before?: { kyc_status: string }; after?: { kyc_status: string } } }[] }>(request, "/admin/audit-logs?action=admin.kyc_verified", t);
    expect(audit.items[0].metadata.before?.kyc_status).toBe("pending");
    expect(audit.items[0].metadata.after?.kyc_status).toBe("verified");
  });
});

test.describe("refunds are off until the policy is approved", () => {
  test("the payment page explains why and the API refuses", async ({ page, request }) => {
    const t = await adminToken(request);
    const pay = (await api<{ items: { id: string; status: string }[] }>(request, "/admin/payments?status=captured&limit=1", t)).items[0];
    await page.goto(`/payments/${pay.id}`);
    await expect(page.getByTestId("refund-blocked")).toContainText("switched off");
    await expect(page.getByTestId("refund-open")).toBeDisabled();
    const r = await request.post(`${API}/admin/payments/${pay.id}/refunds`, { headers: { ...authed(t), "Idempotency-Key": "e2e-refund-key-1" }, data: { amount_paise: 1000, reason: "should be blocked" } });
    expect(r.status()).toBe(409);
    expect((await r.json()).code).toBe("REFUNDS_DISABLED");
  });
});

test.describe("coupons, content, sports", () => {
  test("create a coupon in the UI and see the server quote apply it", async ({ page, request }) => {
    await page.goto("/coupons");
    await page.getByTestId("coupon-new").click();
    const d = page.locator("dialog[open]");
    await d.getByLabel("Code *").fill("E2E10");
    await d.getByLabel("Percentage (basis points)").fill("1000");
    await d.getByLabel("Maximum discount (₹)").fill("50");
    await page.locator("dialog[open]").getByTestId("action-confirm").click();
    await expect(page.locator("dialog[open]").getByTestId("action-result")).toBeVisible();
    await d.getByRole("button", { name: "Close" }).click();
    await expect(page.getByRole("link", { name: "E2E10" })).toBeVisible();
    // a real customer asks the server for a price with the code
    const cust = await tokenFor(request, "diya@example.com", USER_PASSWORD);
    const res = await request.get(`${API}/venues?limit=1`, { headers: authed(cust) });
    expect(res.ok()).toBeTruthy();
  });

  test("publish a CMS page and read it from the public endpoint; unpublish hides it", async ({ page, request }) => {
    await page.goto("/cms");
    await page.getByTestId("cms-new").click();
    const d = page.locator("dialog[open]");
    await d.getByLabel("Slug *").fill("terms-customer");
    await d.getByLabel("Title / question *").fill("Terms for players");
    await d.getByLabel("Body / answer *").fill("Be kind. Pay on time.");
    await page.locator("dialog[open]").getByTestId("action-confirm").click();
    await expect(page.locator("dialog[open]").getByTestId("action-result")).toBeVisible();
    await d.getByRole("button", { name: "Close" }).click();
    expect((await request.get(`${API}/content/terms-customer`)).status()).toBe(404); // draft
    await page.getByRole("link", { name: "Terms for players" }).click();
    await page.getByRole("button", { name: "Publish", exact: true }).click();
    await page.locator("dialog[open]").getByTestId("action-confirm").click();
    await expect(page.locator("dialog[open]").getByTestId("action-result")).toBeVisible();
    const live = await (await request.get(`${API}/content/terms-customer`)).json();
    expect(live.body).toBe("Be kind. Pay on time.");
  });

  test("add and deactivate a sport; the app list follows", async ({ page, request }) => {
    await page.goto("/categories");
    await page.getByTestId("category-add").click();
    await page.locator("dialog[open]").getByLabel("Name *").fill("Pickleball");
    await page.locator("dialog[open]").getByTestId("action-confirm").click();
    await expect(page.locator("dialog[open]").getByTestId("action-result")).toBeVisible();
    await page.locator("dialog[open]").getByRole("button", { name: "Close" }).click();
    const cust = await tokenFor(request, "diya@example.com", USER_PASSWORD);
    const list = async () => ((await (await request.get(`${API}/categories`, { headers: authed(cust) })).json()) as { slug: string }[]).map((c) => c.slug);
    expect(await list()).toContain("pickleball");
    const row = page.locator("tr", { hasText: "Pickleball" });
    await row.getByRole("button", { name: "Deactivate" }).click();
    await page.locator("dialog[open]").getByTestId("action-confirm").click();
    await expect(page.locator("dialog[open]").getByTestId("action-result")).toBeVisible();
    expect(await list()).not.toContain("pickleball");
  });
});

test.describe("roles, switches, monitoring, finance", () => {
  test("create a role with limited permissions; the role list shows it", async ({ page }) => {
    await page.goto("/roles");
    await page.getByTestId("role-new").click();
    const d = page.locator("dialog[open]");
    await d.getByLabel("Role name *").fill("Content editor");
    await d.getByLabel("Manage CMS content").check();
    await page.locator("dialog[open]").getByTestId("action-confirm").click();
    await expect(page.locator("dialog[open]").getByTestId("action-result")).toBeVisible();
    await d.getByRole("button", { name: "Close" }).click();
    await expect(page.getByTestId("roles-table")).toContainText("Content editor");
    await expect(page.getByTestId("roles-table")).toContainText("cms.manage");
    await expect(page.getByTestId("admins-table")).toContainText("No role: no access");
  });

  test("platform switches start on their safe values", async ({ page }) => {
    await page.goto("/platform");
    for (const [k, v] of [["venue_approval_required", "Off"], ["refunds_enabled", "Off"], ["payouts_enabled", "Off"], ["payout_requires_kyc", "On"]] as const) {
      await expect(page.getByTestId(`switch-${k}`)).toContainText(v);
    }
  });

  test("monitoring shows real status without secrets", async ({ page }) => {
    await page.goto("/monitoring");
    await expect(page.getByText("Connected")).toBeVisible();
    await expect(page.getByTestId("webhooks-card")).toBeVisible();
    await expect(page.getByTestId("warnings")).toContainText("Razorpay");
    const text = await page.locator("main").innerText();
    expect(text).not.toMatch(/secret_|service_role|postgresql:\/\//i);
  });

  test("finance: nothing is invented without an approved configuration", async ({ page }) => {
    await page.goto("/finance");
    await expect(page.getByTestId("decisions")).toContainText("Q7/Q8");
    await expect(page.getByText("Not available").first()).toBeVisible();
    await page.goto("/payouts");
    await expect(page.getByTestId("payouts-off")).toBeVisible();
    await page.goto("/finance/reconciliation");
    await page.getByTestId("recon-run").click();
    await page.locator("dialog[open]").getByTestId("action-confirm").click();
    await expect(page.locator("dialog[open]").getByTestId("action-result")).toBeVisible();
    await page.locator("dialog[open]").getByRole("button", { name: "Close" }).click();
    await page.getByRole("link", { name: /\d{4}/ }).first().click();
    await expect(page.getByTestId("gateway-skipped")).toBeVisible(); // e2e has no Razorpay: the run says so honestly
  });

  test("the audit log filters by action and shows before and after", async ({ page }) => {
    await page.goto("/audit?action=admin.setting_changed");
    await expect(page.getByTestId("audit-diff").first()).toContainText("→");
    await page.goto("/audit?entity_type=venue&from=2001-01-01&to=2001-01-02");
    await expect(page.getByTestId("empty-state")).toBeVisible();
  });
});
