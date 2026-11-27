import type { Metadata } from "next";
import { ActionButton, REASON } from "@/components/data/action-button";
import { FinanceTabs } from "@/components/data/finance-tabs";
import { PageHeader } from "@/components/data/page-header";
import { StatusBadge } from "@/components/data/status-badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Alert } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { hasPermission } from "@/lib/admin-access";
import { formatDateTime, formatMoney, titleCase } from "@/lib/format";

export const metadata: Metadata = { title: "Fees, tax and commission" };
type C = { id: string; version: number; status: string; platform_fee_bps: number; platform_fee_fixed_paise: number; tax_rate_bps: number; tax_on: string; commission_bps: number; discount_borne_by: string; commission_base: string; notes: string | null; created_at: string; approved_at: string | null; effective_from: string | null };
const pct = (bps: number) => `${(bps / 100).toFixed(2).replace(/\.?0+$/, "")}%`;

export default async function ConfigsPage() {
  const [res, canManage, canApprove] = await Promise.all([safe(adminGet<{ items: C[] }>("/admin/finance/configs")), hasPermission("finance.manage"), hasPermission("finance.approve")]);
  const back = ["/finance/configs", "/finance"];
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader title="Fees, tax and commission" description="Versioned rules. A draft does nothing. An approved version is immutable: to change a rate, approve a new version."
        actions={canManage && <ActionButton label="Draft a new version" title="Draft a configuration" path="/admin/finance/configs" variant="default" refresh={back} testId="config-new"
          description="Enter the rates the business decided (Q7, Q8). Nothing changes for customers or owners until a different administrator approves it."
          fields={[{ name: "platform_fee_bps", label: "Platform fee (basis points of the slot price)", type: "number", required: true, defaultValue: 0, min: 0, max: 10000, help: "500 = 5%. The customer pays this on top of the slot price." },
            { name: "platform_fee_fixed_paise", label: "Fixed platform fee per booking (₹)", type: "money", defaultValue: "0" },
            { name: "tax_rate_bps", label: "Tax rate (basis points)", type: "number", required: true, defaultValue: 0, min: 0, max: 10000, help: "1800 = 18%." },
            { name: "tax_on", label: "Tax is charged on", type: "select", required: true, options: [{ value: "fee", label: "The platform fee only" }, { value: "base_and_fee", label: "Slot price + platform fee" }], help: "Ask the accountant: this is part of Q7." },
            { name: "commission_bps", label: "Fallback commission (basis points)", type: "number", required: true, defaultValue: 0, min: 0, max: 10000, help: "Used only when no commission rule (venue, activity or global) applies. Manage the real rules under Commission (Q8)." },
            { name: "commission_base", label: "Commission is calculated on", type: "select", required: true, defaultValue: "base", options: [{ value: "base", label: "The slot price, before discounts, fees and tax" }, { value: "base_after_discount", label: "The slot price after the coupon discount" }], help: "Open decision (Q7/Q8). The first option is how it worked before commission rules existed." },
            { name: "discount_borne_by", label: "Coupon discounts are paid by", type: "select", required: true, options: [{ value: "platform", label: "ZURUV (owner still gets the full share)" }, { value: "owner", label: "The owner (their share is reduced)" }] },
            { name: "notes", label: "Notes (who decided, when)", type: "textarea", maxLength: 1000 }]} />} />
      <FinanceTabs current="/finance/configs" />
      <Alert variant="info">Rounding is half-up to the paisa. Approval needs a different administrator from the one who drafted it. Payments captured before a version is approved are never re-priced.</Alert>
      <Card>
        {!res.ok ? <div className="p-4"><ErrorState message={`Could not load configurations (${res.error.message}).`} /></div> : res.data.items.length === 0 ? <EmptyState title="No configuration yet" description="Fees, tax and commission are all zero until one is approved." /> : (
          <Table>
            <THead><TR><TH>Version</TH><TH>Status</TH><TH>Platform fee</TH><TH>Tax</TH><TH>Fallback commission</TH><TH>Discounts paid by</TH><TH>Effective from</TH><TH>Action</TH></TR></THead>
            <TBody>{res.data.items.map((c) => (
              <TR key={c.id}>
                <TD className="font-medium">v{c.version}{c.notes && <p className="max-w-xs text-xs font-normal text-muted-foreground">{c.notes}</p>}</TD>
                <TD><StatusBadge status={c.status === "draft" ? "draft" : c.status === "approved" ? "active" : "expired"} /><span className="ml-1 text-xs text-muted-foreground">{titleCase(c.status)}</span></TD>
                <TD>{pct(c.platform_fee_bps)}{c.platform_fee_fixed_paise > 0 && ` + ${formatMoney(c.platform_fee_fixed_paise)}`}</TD>
                <TD>{pct(c.tax_rate_bps)} on {c.tax_on === "fee" ? "fee" : "price + fee"}</TD><TD>{pct(c.commission_bps)}<p className="text-xs text-muted-foreground">on {c.commission_base === "base" ? "slot price" : "price after discount"}</p></TD><TD>{titleCase(c.discount_borne_by)}</TD>
                <TD className="whitespace-nowrap text-xs">{formatDateTime(c.effective_from)}</TD>
                <TD>{c.status === "draft" && (
                  <div className="flex gap-2">
                    {canApprove && <ActionButton label="Approve" title={`Approve version ${c.version}?`} path={`/admin/finance/configs/${c.id}/approve`} fields={[REASON]} variant="default" refresh={back} testId="config-approve"
                      description="From this moment new bookings are priced with these rules and new payments are split by them. This cannot be edited or undone; supersede it with a new version." />}
                    {canManage && <ActionButton label="Delete draft" method="DELETE" path={`/admin/finance/configs/${c.id}`} danger refresh={back} title="Delete this draft?" />}
                  </div>
                )}</TD>
              </TR>
            ))}</TBody>
          </Table>
        )}
      </Card>
    </div>
  );
}
