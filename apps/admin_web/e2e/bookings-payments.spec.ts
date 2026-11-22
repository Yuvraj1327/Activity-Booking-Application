import { expect, test } from "@playwright/test";
import { adminToken, api } from "./support/helpers";

const rows = (page: import("@playwright/test").Page) => page.locator("tbody tr");
type B = { items: { id: string; booking_code: string; status: string; payment_status: string; venue_name: string; customer_name: string }[]; has_more: boolean };

test.describe("bookings", () => {
  test("table shows the required columns and the first page is paginated", async ({ page }) => {
    await page.goto("/bookings");
    for (const h of ["Booking", "Customer", "Venue / owner", "Date & time", "Duration", "Amount", "Payment", "Status", "Created"]) {
      await expect(page.getByRole("columnheader", { name: h })).toBeVisible();
    }
    await expect(rows(page)).toHaveCount(20);
    await expect(page.getByText("Page 1")).toBeVisible();
    await page.getByRole("link", { name: "Next" }).click();
    await expect(page).toHaveURL(/page=2/);
    await expect(rows(page)).toHaveCount(13); // 33 bookings in total
    await expect(page.getByText("Page 2")).toBeVisible();
    await expect(page.getByRole("link", { name: "Next" })).toHaveCount(0);
    await page.getByRole("link", { name: "Previous" }).click();
    await expect(rows(page)).toHaveCount(20);
  });

  test("search by booking ID/code, filter by status, payment status, venue and date", async ({ page, request }) => {
    const t = await adminToken(request);
    const all = await api<B>(request, "/admin/bookings?limit=50", t);
    const code = all.items[3].booking_code;
    await page.goto("/bookings");
    await page.getByPlaceholder("Booking ID, customer or venue").fill(code.toLowerCase());
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(rows(page)).toHaveCount(1);
    await expect(rows(page).first()).toContainText(code);

    await page.goto("/bookings?status=pending_payment");
    await expect(rows(page)).toHaveCount(1);
    await page.goto("/bookings?status=cancelled_by_customer");
    await expect(rows(page)).toHaveCount(1);
    await page.goto("/bookings?payment_status=failed");
    await expect(rows(page)).toHaveCount(1);
    await page.goto("/bookings?payment_status=paid");
    await expect(page.getByText("Page 1")).toBeVisible();
    await page.getByLabel("Booking status").selectOption("confirmed");
    await page.getByLabel("Payment status").selectOption("paid");
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(page).toHaveURL(/status=confirmed/);
    await page.goto("/bookings?from=2001-01-01&to=2001-01-02");
    await expect(page.getByTestId("empty-state")).toBeVisible();
    await page.goto("/bookings?q=smash");
    for (const r of await rows(page).all()) await expect(r).toContainText("Smash Arena");
  });

  test("detail shows customer, owner, venue, amounts, payment records and the full timeline", async ({ page, request }) => {
    const t = await adminToken(request);
    const paid = (await api<B>(request, "/admin/bookings?status=confirmed&limit=1", t)).items[0];
    await page.goto(`/bookings/${paid.id}`);
    await expect(page.getByRole("heading", { name: paid.booking_code })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Payment records" })).toBeVisible();
    await expect(page.getByTestId("amount-breakdown")).toContainText("Total charged");
    await expect(page.getByRole("heading", { name: "Customer", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Owner", exact: true })).toBeVisible();
    await expect(page.getByTestId("timeline")).toContainText("Pending payment → Confirmed");
    // the only status action an admin has is an exceptional cancellation, and it needs a reason
    await expect(page.getByRole("button", { name: "Cancel booking" })).toBeVisible();
    await expect(page.getByRole("button", { name: /^(confirm|complete|mark)/i })).toHaveCount(0);
    const pending = (await api<B>(request, "/admin/bookings?status=pending_payment&limit=1", t)).items[0];
    await page.goto(`/bookings/${pending.id}`);
    await expect(page.getByText("No payment started")).toBeVisible();
  });

  test("admin API offers no way to change a booking's status", async ({ request }) => {
    const t = await adminToken(request);
    const b = (await api<B>(request, "/admin/bookings?status=confirmed&limit=1", t)).items[0];
    for (const method of ["PATCH", "PUT", "POST", "DELETE"] as const) {
      const r = await request.fetch(`http://127.0.0.1:8018/api/v1/admin/bookings/${b.id}`, { method, headers: { Authorization: `Bearer ${t}` }, data: { status: "cancelled_by_owner" } });
      expect([404, 405]).toContain(r.status());
    }
    const after = await api<{ status: string }>(request, `/admin/bookings/${b.id}`, t);
    expect(after.status).toBe("confirmed");
  });
});

test.describe("payments", () => {
  test("payments page distinguishes successful, failed and pending, and summarises refunds", async ({ page, request }) => {
    const s = await api<{ captured_count: number; failed_count: number; open_count: number; gross_captured_paise: number }>(request, "/admin/payments/summary", await adminToken(request));
    await page.goto("/payments");
    const stat = (l: string) => page.getByTestId("stat-card").filter({ has: page.getByText(l, { exact: true }) }).getByTestId("stat-value");
    await expect(stat("Failed")).toHaveText(String(s.failed_count));
    await expect(stat("Pending / open")).toHaveText(String(s.open_count));
    await expect(stat("Successful payments")).toContainText("₹");
    await expect(page.getByTestId("refund-summary")).toContainText("Refunds:");
    for (const h of ["Payment", "Booking", "Venue", "Amount", "Method", "Status", "Refunded", "Gateway reference", "Date"]) {
      await expect(page.getByRole("columnheader", { name: h })).toBeVisible();
    }
    await expect(rows(page)).toHaveCount(s.captured_count + s.failed_count + s.open_count > 20 ? 20 : s.captured_count + s.failed_count + s.open_count);
    await expect(page.getByText("INR").first()).toBeVisible();
  });

  test("search by gateway reference and booking code; filter by status and date", async ({ page, request }) => {
    const t = await adminToken(request);
    const list = await api<{ items: { razorpay_payment_id: string | null; booking_code: string; status: string }[] }>(request, "/admin/payments?status=captured&limit=5", t);
    const ref = list.items[0].razorpay_payment_id!;
    await page.goto("/payments");
    await page.getByPlaceholder("Booking ID, payment ID or gateway reference").fill(ref);
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(rows(page)).toHaveCount(1);
    await expect(rows(page).first()).toContainText(ref);
    await page.goto(`/payments?q=${list.items[1].booking_code}`);
    await expect(rows(page)).toHaveCount(1);
    await page.goto("/payments?status=failed");
    await expect(rows(page)).toHaveCount(1);
    await expect(rows(page).first()).toContainText("Failed");
    await page.goto("/payments?from=2001-01-01&to=2001-01-02");
    await expect(page.getByTestId("empty-state")).toBeVisible();
  });

  test("payment detail shows the gateway record and events, with no secrets", async ({ page, request }) => {
    const t = await adminToken(request);
    const p = (await api<{ items: { id: string }[] }>(request, "/admin/payments?status=captured&limit=1", t)).items[0];
    await page.goto(`/payments/${p.id}`);
    await expect(page.getByRole("heading", { name: "Gateway events" })).toBeVisible();
    await expect(page.getByText("Razorpay order")).toBeVisible();
    const html = await page.content();
    expect(html).not.toMatch(/key_secret|webhook_secret|service[_-]role/i);
  });
});

test.describe("CSV export", () => {
  test("bookings export downloads, respects filters, and omits contact details", async ({ page }) => {
    await page.goto("/bookings?status=confirmed");
    const [dl] = await Promise.all([page.waitForEvent("download"), page.getByTestId("export-bookings").click()]);
    expect(dl.suggestedFilename()).toBe("zuruv-bookings.csv");
    const csv = (await (await import("node:fs")).promises.readFile((await dl.path())!, "utf8")).split("\r\n").filter(Boolean);
    expect(csv[0]).toBe("booking_code,booking_id,customer_id,customer_name,venue,owner_name,booking_date,start_local,end_local,duration_minutes,total_amount_paise,currency,payment_status,booking_status,created_at_utc,city,sports,refund_status,refunded_paise");
    expect(csv.length - 1).toBe(30);
    expect(csv.slice(1).every((l) => l.endsWith("") && l.includes(",confirmed,"))).toBeTruthy();
    expect(csv.join("\n")).not.toMatch(/@example\.com|\+91\d{8}/);
  });

  test("payments export and the customer/owner reports download; exports are audited", async ({ page, request }) => {
    await page.goto("/payments");
    const [d1] = await Promise.all([page.waitForEvent("download"), page.getByTestId("export-payments").click()]);
    const fs = await import("node:fs");
    const pay = fs.readFileSync((await d1.path())!, "utf8");
    expect(pay.split("\r\n")[0]).toContain("razorpay_payment_id");
    expect(pay.split("\r\n").filter(Boolean).length).toBe(32); // header + 31 payments
    await page.goto("/customers");
    const [d2] = await Promise.all([page.waitForEvent("download"), page.getByTestId("export-customers").click()]);
    const cust = fs.readFileSync((await d2.path())!, "utf8");
    expect(cust.split("\r\n")[0]).toBe("id,name,status,registered_at_utc,bookings_count");
    expect(cust).not.toContain("@");
    await page.goto("/owners");
    const [d3] = await Promise.all([page.waitForEvent("download"), page.getByTestId("export-owners").click()]);
    expect(fs.readFileSync((await d3.path())!, "utf8").split("\r\n").filter(Boolean).length).toBe(5);
    const audit = await api<{ items: { entity_type: string; metadata: { rows: number } }[] }>(request, "/admin/audit-logs?action=admin.export&limit=10", await adminToken(request));
    expect(new Set(audit.items.map((a) => a.entity_type))).toEqual(new Set(["bookings", "payments", "customers", "owners"]));
  });
});
