import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ActionButton } from "@/components/data/action-button";
import { CommissionTabs } from "@/components/data/commission-tabs";
import { SCOPE_LABEL, bpsHelp } from "@/lib/commission";
import { visibleGroups } from "@/lib/nav";

const run = vi.fn();
vi.mock("@/app/admin-actions", () => ({ runAdminAction: (...a: unknown[]) => run(...a) }));

beforeEach(() => {
  run.mockReset();
  run.mockResolvedValue({ ok: true, message: "Done." });
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); };
});

describe("commission navigation and labels", () => {
  it("Commission appears only for admins who may view it", () => {
    const names = (p: string[]) => visibleGroups(p).flatMap((g) => g.items.map((i) => i.label));
    expect(names(["finance.view"])).not.toContain("Commission");
    expect(names(["commission.view"])).toContain("Commission");
  });
  it("names every rule scope the API can return and explains the unit", () => {
    for (const s of ["venue", "activity", "global", "finance_config", "none", "legacy"]) expect(SCOPE_LABEL[s]).toBeTruthy();
    expect(bpsHelp).toContain("1000 = 10%");
  });
  it("tabs mark the current section", () => {
    render(<CommissionTabs current="/commission/history" />);
    expect(screen.getByRole("link", { name: "History" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Rules" })).not.toHaveAttribute("aria-current");
  });
});

describe("a commission rule form sends exactly what the API expects", () => {
  it("creates a venue rule: fixed scope + venue, basis points as a number, and a reason", async () => {
    render(
      <ActionButton label="Set commission" path="/admin/commission/rules" fixed={{ scope: "venue", venue_id: "v-1", is_active: true }}
        fields={[{ name: "commission_bps", label: "Commission (basis points)", type: "number", required: true, min: 0, max: 10000 }, { name: "effective_from", label: "Effective from", type: "datetime" }, { name: "reason", label: "Reason", type: "textarea", required: true }]} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Set commission" }));
    await userEvent.type(screen.getByLabelText(/Commission \(basis points\)/), "1250");
    await userEvent.type(screen.getByLabelText(/Reason/), "Negotiated rate");
    await userEvent.click(screen.getByTestId("action-confirm"));
    const fd = run.mock.calls[0][1] as FormData;
    expect(fd.get("path")).toBe("/admin/commission/rules");
    expect(JSON.parse(String(fd.get("payload")))).toEqual({ scope: "venue", venue_id: "v-1", is_active: true, commission_bps: 1250, reason: "Negotiated rate" });
  });
  it("deactivating sends is_active=false and requires a reason", async () => {
    render(<ActionButton label="Deactivate" path="/admin/commission/rules/r1/versions" fixed={{ is_active: false }} fields={[{ name: "reason", label: "Reason", type: "textarea", required: true }]} />);
    await userEvent.click(screen.getByRole("button", { name: "Deactivate" }));
    await userEvent.click(screen.getByTestId("action-confirm"));
    expect(run).not.toHaveBeenCalled(); // blocked: no reason
    await userEvent.type(screen.getByLabelText(/Reason/), "Promotion over");
    await userEvent.click(screen.getByTestId("action-confirm"));
    expect(JSON.parse(String((run.mock.calls[0][1] as FormData).get("payload")))).toEqual({ is_active: false, reason: "Promotion over" });
  });
});
