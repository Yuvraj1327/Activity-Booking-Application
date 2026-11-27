import type { Metadata } from "next";
import { CommissionTabs } from "@/components/data/commission-tabs";
import { DateRangeFilter } from "@/components/data/date-range-filter";
import { ExportButton } from "@/components/data/export-button";
import { PageHeader } from "@/components/data/page-header";
import { StatCard } from "@/components/data/stat-card";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Alert } from "@/components/ui/alert";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { SCOPE_LABEL, type CommissionReport, type Totals } from "@/lib/commission";
import { formatMoney, formatNumber } from "@/lib/format";
import { resolveRange, type SearchParams } from "@/lib/query";

export const metadata: Metadata = { title: "Commission reports" };

function Rows({ rows, label }: { rows: (Totals & { key: string; name: string })[]; label: string }) {
  if (rows.length === 0) return <EmptyState title="No commission in this period" description="Entries exist only for payments captured under an approved finance configuration." />;
  return (
    <Table>
      <THead><TR><TH>{label}</TH><TH className="text-right">Bookings</TH><TH className="text-right">Gross booked</TH><TH className="text-right">Refunded</TH><TH className="text-right">Net commission</TH><TH className="text-right">Owner net payable</TH></TR></THead>
      <TBody>{rows.map((r) => (
        <TR key={r.key}><TD className="font-medium">{r.name}</TD><TD className="text-right tabular-nums">{formatNumber(r.bookings)}</TD><TD className="text-right tabular-nums">{formatMoney(r.sales_gross_paise)}</TD><TD className="text-right tabular-nums">{formatMoney(r.refunded_gross_paise)}</TD><TD className="text-right font-medium tabular-nums">{formatMoney(r.net_commission_paise)}</TD><TD className="text-right tabular-nums">{formatMoney(r.owner_net_paise)}</TD></TR>
      ))}</TBody>
    </Table>
  );
}

export default async function ReportPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const range = resolveRange(params);
  const res = await safe(adminGet<CommissionReport>("/admin/commission/report", { from: range.from, to: range.to }));
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader title="Commission reports" description="Built from the immutable ledger. Refunds reverse commission, and a repeated payment event is never counted twice."
        actions={<ExportButton kind="commission" query={{ from: range.from, to: range.to }} label="Export CSV" />} />
      <CommissionTabs current="/commission/report" />
      <DateRangeFilter path="/commission/report" params={params} range={range} />
      {!res.ok ? <ErrorState message={`Could not load the report (${res.error.message}).`} /> : (() => {
        const r = res.data;
        const t = r.totals;
        return (
          <>
            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Commission totals">
              <StatCard label="Gross booking value" value={formatMoney(t.net_gross_paise)} hint={`${formatMoney(t.sales_gross_paise)} paid − ${formatMoney(t.refunded_gross_paise)} refunded · ${t.bookings} bookings`} />
              <StatCard label="Platform commission" value={formatMoney(t.net_commission_paise)} hint={`${formatMoney(t.commission_accrued_paise)} accrued − ${formatMoney(t.commission_reversed_paise)} reversed by refunds`} tone="success" />
              <StatCard label="Owner net payable" value={formatMoney(t.owner_net_paise)} hint="A record of what is owed. Not a transfer: payouts are separate." />
              <StatCard label="Tax held" value={formatMoney(t.tax_paise)} hint="Not part of commission" tone="warning" />
            </section>
            <Alert variant={r.reconciliation.ok ? "info" : "error"} data-testid="reconciliation">
              <p className="font-medium">{r.reconciliation.ok ? "Commission totals reconcile with payment and refund records." : "Reconciliation found differences. Investigate before relying on these totals."}</p>
              <ul className="mt-1 space-y-0.5 text-sm">{r.reconciliation.checks.map((c) => <li key={c.key}>{c.ok ? "✓" : "✗"} {c.label}{c.mismatches > 0 && ` — ${c.mismatches}`}</li>)}</ul>
            </Alert>
            <Card><CardHeader><CardTitle>By rule scope</CardTitle><CardDescription>Which kind of rule produced the commission.</CardDescription></CardHeader>
              <Rows label="Rule" rows={r.by_scope.map((x) => ({ ...x, key: x.scope, name: SCOPE_LABEL[x.scope] ?? x.scope }))} /></Card>
            <Card><CardHeader><CardTitle>By activity</CardTitle><CardDescription>A booking counts under the sport that decided its rule, otherwise the venue&apos;s first listed sport.</CardDescription></CardHeader>
              <Rows label="Activity" rows={r.by_activity.map((x) => ({ ...x, key: x.category_id ?? "none", name: x.category_name }))} /></Card>
            <Card><CardHeader><CardTitle>By venue</CardTitle></CardHeader>
              <Rows label="Venue" rows={r.by_venue.map((x) => ({ ...x, key: x.venue_id, name: x.venue_name }))} /></Card>
            <Card><CardHeader><CardTitle>By date</CardTitle><CardDescription>Day the payment or refund was recorded.</CardDescription></CardHeader>
              <Rows label="Date" rows={r.by_day.map((x) => ({ ...x, key: x.date, name: x.date }))} /></Card>
          </>
        );
      })()}
    </div>
  );
}
