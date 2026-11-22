import type { Metadata } from "next";
import Link from "next/link";
import { ActionButton, REASON } from "@/components/data/action-button";
import { ExportButton } from "@/components/data/export-button";
import { FilterBar } from "@/components/data/filter-bar";
import { FinanceTabs } from "@/components/data/finance-tabs";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { StatusBadge } from "@/components/data/status-badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Alert } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { hasPermission } from "@/lib/admin-access";
import { formatDateTime, formatMoney, titleCase } from "@/lib/format";
import { one, PAGE_SIZE, pageOf, type SearchParams } from "@/lib/query";
import type { Cursor } from "@/lib/types";

export const metadata: Metadata = { title: "Owner payouts" };
type P = { id: string; owner_id: string; owner_name: string; amount_paise: number; status: string; period_from: string | null; period_to: string | null; method: string | null; reference: string | null; paid_at: string | null; created_at: string; note: string | null };

export default async function PayoutsPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const { offset, page } = pageOf(params);
  const [res, can, settings] = await Promise.all([
    safe(adminGet<Cursor<P> & { items: P[] }>("/admin/payouts", { status: one(params, "status"), owner_id: one(params, "owner_id"), limit: PAGE_SIZE, offset })),
    hasPermission("payouts.manage"), safe(adminGet<{ items: { key: string; value: boolean }[] }>("/admin/settings")),
  ]);
  const enabled = settings.ok ? settings.data.items.find((s) => s.key === "payouts_enabled")?.value : undefined;
  const back = ["/payouts"];
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader title="Owner payouts" description="Payout records and their history. Marking a payout paid records a transfer made outside this system; no money is sent from here."
        actions={<>
          <ExportButton kind="payouts" query={{ owner_id: one(params, "owner_id") }} />
          {can && <ActionButton label="New payout" title="Create a payout record" path="/admin/payouts" variant="default" refresh={back} testId="payout-new" disabled={enabled === false} disabledReason="Payouts are switched off (Q10)."
            description="The amount cannot exceed what the owner has earned and not yet been paid or reserved. A different administrator approves it."
            fields={[{ name: "owner_id", label: "Owner ID", required: true, placeholder: "Paste from the owner's page URL" }, { name: "amount_paise", label: "Amount (₹)", type: "money", required: true },
              { name: "period_from", label: "Period from", type: "date" }, { name: "period_to", label: "Period to", type: "date" }, { name: "note", label: "Note", maxLength: 500 }]} />}
        </>} />
      <FinanceTabs current="/payouts" />
      {enabled === false && <Alert variant="info" data-testid="payouts-off">Payouts are switched off until the payout rules (Q10) are approved. Turn them on under Platform switches. Automatic payouts through Razorpay are not integrated: this tracks transfers made by your team.</Alert>}
      <Card>
        <FilterBar path="/payouts" params={params} fields={[{ kind: "select", name: "status", label: "Status", options: ["draft", "approved", "paid", "cancelled"] }]} />
        {!res.ok ? <div className="p-4"><ErrorState message={`Could not load payouts (${res.error.message}).`} /></div> : res.data.items.length === 0 ? <EmptyState title="No payouts recorded" /> : (
          <>
            <Table>
              <THead><TR><TH>Owner</TH><TH className="text-right">Amount</TH><TH>Status</TH><TH>Period</TH><TH>Transfer</TH><TH>Created</TH><TH>Actions</TH></TR></THead>
              <TBody>{res.data.items.map((p) => (
                <TR key={p.id}>
                  <TD><Link href={`/owners/${p.owner_id}#payouts`} className="font-medium text-primary hover:underline">{p.owner_name}</Link>{p.note && <p className="text-xs text-muted-foreground">{p.note}</p>}</TD>
                  <TD className="text-right tabular-nums">{formatMoney(p.amount_paise)}</TD><TD><StatusBadge status={p.status === "paid" ? "paid" : p.status} /></TD>
                  <TD className="text-xs">{p.period_from ?? "—"} → {p.period_to ?? "—"}</TD>
                  <TD className="text-xs">{p.reference ? <>{titleCase(p.method ?? "")} · <span className="font-mono">{p.reference}</span><br />{formatDateTime(p.paid_at)}</> : "—"}</TD>
                  <TD className="whitespace-nowrap text-xs">{formatDateTime(p.created_at)}</TD>
                  <TD>{can && (
                    <div className="flex flex-wrap gap-2">
                      {p.status === "draft" && <ActionButton label="Approve" title="Approve this payout?" path={`/admin/payouts/${p.id}/approve`} refresh={back} description="A different administrator from the one who created it." />}
                      {p.status === "approved" && <ActionButton label="Record as paid" title="Record the transfer" path={`/admin/payouts/${p.id}/paid`} variant="default" refresh={back} description="Do this AFTER the money has been sent. Enter the bank / UPI reference so it can be matched later."
                        fields={[{ name: "method", label: "Method", type: "select", required: true, options: [{ value: "bank_transfer", label: "Bank transfer" }, { value: "upi", label: "UPI" }, { value: "other", label: "Other" }] }, { name: "reference", label: "Transfer reference (UTR / transaction id)", required: true, maxLength: 100 }]} />}
                      {(p.status === "draft" || p.status === "approved") && <ActionButton label="Cancel" path={`/admin/payouts/${p.id}/cancel`} danger fields={[REASON]} refresh={back} title="Cancel this payout?" />}
                    </div>
                  )}</TD>
                </TR>
              ))}</TBody>
            </Table>
            <Pagination path="/payouts" params={params} page={page} hasMore={res.data.has_more} shown={res.data.items.length} />
          </>
        )}
      </Card>
    </div>
  );
}
