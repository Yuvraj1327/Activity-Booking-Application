import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ActionButton, rupeesToPaise, REASON } from "@/components/data/action-button";
import { MoneyPanel } from "@/components/data/money-panel";
import { StatusBadge } from "@/components/data/status-badge";
import { paiseToRupees, toneOf } from "@/lib/format";
import { navGroups, visibleGroups } from "@/lib/nav";
import type { Money } from "@/lib/types";

const run = vi.fn();
vi.mock("@/app/admin-actions", () => ({ runAdminAction: (...a: unknown[]) => run(...a) }));

beforeEach(() => {
  run.mockReset();
  run.mockResolvedValue({ ok: true, message: "Done." });
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); };
});

describe("money in rupees <-> integer paise", () => {
  it("accepts plain amounts and rejects everything else", () => {
    expect(rupeesToPaise("250")).toBe(25000);
    expect(rupeesToPaise("250.5")).toBe(25050);
    expect(rupeesToPaise("0.07")).toBe(7);
    expect(rupeesToPaise("19.99")).toBe(1999);
    for (const bad of ["", "abc", "-5", "1,000", "1.234", "1e3", "₹5"]) expect(Number.isNaN(rupeesToPaise(bad))).toBe(true);
    expect(paiseToRupees(25000)).toBe("250");
    expect(paiseToRupees(25050)).toBe("250.50");
    expect(paiseToRupees(null)).toBe("");
  });
});

describe("navigation follows permissions", () => {
  it("shows only entries the admin may open, and nothing without a role", () => {
    expect(visibleGroups([])).toEqual([]);
    const names = (p: string[]) => visibleGroups(p).flatMap((g) => g.items.map((i) => i.label));
    expect(names(["support.manage"])).toEqual(["Support tickets", "Notifications"]);
    expect(names(["support.manage", "refunds.manage"])).not.toContain("Refunds"); // refunds needs payments.view to be visited
    const all = navGroups.flatMap((g) => g.items.filter((i) => i.perm).map((i) => i.perm as string));
    expect(names(all)).toHaveLength(navGroups.flatMap((g) => g.items).length);
  });
});

describe("statuses", () => {
  it("new states have a tone and a readable label", () => {
    expect(toneOf("pending_review")).toBe("warning");
    expect(toneOf("cancelled_by_admin")).toBe("danger");
    expect(toneOf("processed")).toBe("success");
    render(<StatusBadge status="cancelled_by_admin" />);
    expect(screen.getByText("Cancelled by admin")).toBeInTheDocument();
  });
});

describe("money panel", () => {
  const base: Money = {
    currency: "INR", gross_booking_value_paise: 100000, successful_payment_paise: 90000,
    platform_revenue: { available: false, depends_on: "Q7, Q8", message: "x" },
    owner_earnings: { available: false, depends_on: "Q8", message: "x" },
    refunds: { available: true, amount_paise: 5000, note: "Processed by the gateway" },
    tax_collected: { available: false, depends_on: "Q7", message: "x" },
  };
  it("shows a figure only when real data backs it", () => {
    render(<MoneyPanel money={base} />);
    expect(screen.getByTestId("money-platform-revenue")).toHaveTextContent("Not available");
    expect(screen.getByTestId("money-refunds")).toHaveTextContent("₹50.00");
  });
  it("shows ledger figures once a rule is approved, and says how many payments are not covered", () => {
    render(<MoneyPanel money={{ ...base, platform_revenue: { available: true, amount_paise: 6000, note: "ledger" }, owner_earnings: { available: true, amount_paise: 36000, note: "ledger" }, ledger_coverage: { captured_payments: 5, with_ledger_entry: 3, without_ledger_entry: 2 } }} />);
    expect(screen.getByTestId("money-owner-earnings")).toHaveTextContent("₹360.00");
    expect(screen.getByTestId("coverage-note")).toHaveTextContent("2 of 5");
  });
});

describe("ActionButton", () => {
  const open = async () => { await userEvent.click(screen.getByRole("button", { name: "Suspend" })); };

  it("sends the typed values to the audited action, money as integer paise", async () => {
    render(<ActionButton label="Suspend" path="/admin/payouts" fixed={{ owner_id: "o1" }} fields={[{ name: "amount_paise", label: "Amount (₹)", type: "money", required: true }, REASON]} refresh={["/payouts"]} idempotent />);
    await open();
    await userEvent.type(screen.getByLabelText(/Amount/), "123.45");
    await userEvent.type(screen.getByLabelText(/Reason/), "Because we agreed");
    await userEvent.click(screen.getByTestId("action-confirm"));
    expect(run).toHaveBeenCalledTimes(1);
    const fd = run.mock.calls[0][1] as FormData;
    expect(fd.get("method")).toBe("POST");
    expect(fd.get("path")).toBe("/admin/payouts");
    expect(JSON.parse(String(fd.get("payload")))).toEqual({ owner_id: "o1", amount_paise: 12345, reason: "Because we agreed" });
    expect(String(fd.get("idempotency_key")).length).toBeGreaterThanOrEqual(8); // refunds and payouts are retry-safe
    expect(fd.get("refresh")).toBe("/payouts");
  });

  it("does not call the server with an invalid amount", async () => {
    render(<ActionButton label="Suspend" path="/admin/payouts" fields={[{ name: "amount_paise", label: "Amount (₹)", type: "money", required: true }]} />);
    await open();
    await userEvent.type(screen.getByLabelText(/Amount/), "12.345");
    await userEvent.click(screen.getByTestId("action-confirm"));
    expect(screen.getByTestId("action-error")).toHaveTextContent("enter an amount");
    expect(run).not.toHaveBeenCalled();
  });

  it("collects checkboxes and lists, and omits empty optional fields", async () => {
    render(<ActionButton label="Suspend" path="/admin/roles" fields={[
      { name: "permissions", label: "Permissions", type: "checks", options: [{ value: "a.view", label: "A" }, { value: "b.view", label: "B" }] },
      { name: "ids", label: "IDs", type: "list" }, { name: "note", label: "Note" }, { name: "flag", label: "Flag", type: "checkbox" }]} />);
    await open();
    await userEvent.click(screen.getByLabelText("B"));
    await userEvent.type(screen.getByLabelText("IDs"), "x1, x2 x3");
    await userEvent.click(screen.getByTestId("action-confirm"));
    const fd = run.mock.calls[0][1] as FormData;
    expect(JSON.parse(String(fd.get("payload")))).toEqual({ permissions: ["b.view"], ids: ["x1", "x2", "x3"], flag: false });
  });

  it("can be disabled with the reason shown", () => {
    render(<ActionButton label="Suspend" path="/admin/x" disabled disabledReason="Refunds are off" />);
    expect(screen.getByRole("button", { name: "Suspend" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Suspend" })).toHaveAttribute("title", "Refunds are off");
  });
});
