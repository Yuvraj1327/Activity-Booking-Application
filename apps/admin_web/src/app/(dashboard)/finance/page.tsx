import type { Metadata } from "next";
import Link from "next/link";
import { ActionButton } from "@/components/data/action-button";
import { DateRangeFilter } from "@/components/data/date-range-filter";
import { ExportButton } from "@/components/data/export-button";
import { FinanceTabs } from "@/components/data/finance-tabs";
import { PageHeader } from "@/components/data/page-header";
import { StatCard } from "@/components/data/stat-card";
import { ErrorState } from "@/components/data/states";
import { Alert } from "@/components/ui/alert";
import { adminGet, safe } from "@/lib/admin-api";
import { hasPermission } from "@/lib/admin-access";
import { formatDateTime, formatMoney, formatNumber } from "@/lib/format";
import { resolveRange, type SearchParams } from "@/lib/query";

export const metadata: Metadata = { title: "Finance" };

type S = {
  range: { date_from: string; date_to: string };
  active_config: { id: string; version: number; effective_from: string } | null;
  commission?: { net_commission_paise: number; commission_accrued_paise: number; commission_reversed_paise: number; bookings: number; reconciled: boolean } | null;
  ledger: { net_gross: number; owner: number; platform: number; tax: number; sales: number; refunds: number; entries: number } | null;
  coverage: { captured_payments: number; with_ledger_entry: number; without_ledger_entry: number };
  refunds: { processed_paise: number; processed_count: number; in_flight_count: number; failed_count: number };
  payouts: { enabled: boolean; automatic_gateway_payouts: boolean; note: string };
  decisions_needed: string[];
};

export default async function FinancePage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const range = resolveRange(params);
  const [res, canManage] = await Promise.all([safe(adminGet<S>("/admin/finance/summary", { from: range.from, to: range.to })), hasPermission("finance.manage")]);
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader title="Finance" description="Platform revenue, owner earnings, tax and refunds from the immutable ledger. Nothing is shown that an approved rule does not back."
        actions={<><ExportButton kind="ledger" query={{ from: range.from, to: range.to }} label="Export ledger" />
          {canManage && <ActionButton label="Update ledger" title="Write ledger entries now" path="/admin/finance/accrue" refresh={["/finance", "/finance/ledger"]} description="Records every captured payment and processed refund that is not in the ledger yet, using the configuration in force when it happened. Safe to repeat." testId="accrue" />}</>} />
      <FinanceTabs current="/finance" />
      <DateRangeFilter path="/finance" params={params} range={range} />
      {!res.ok ? <ErrorState message={`Could not load finance (${res.error.message}).`} /> : (() => {
        const s = res.data;
        return (
          <>
            {s.decisions_needed.length > 0 && (
              <Alert variant="info" data-testid="decisions"><p className="font-medium">Waiting for the business</p><ul className="mt-1 list-disc pl-5">{s.decisions_needed.map((d) => <li key={d}>{d}</li>)}</ul></Alert>
            )}
            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Ledger totals">
              <StatCard label="Platform revenue" value={s.ledger ? formatMoney(s.ledger.platform) : "Not available"} hint={s.ledger ? "Fees + commission, net of refunds" : "Needs an approved configuration (Q7, Q8)"} />
              <StatCard label="Owner earnings" value={s.ledger ? formatMoney(s.ledger.owner) : "Not available"} hint={s.ledger ? "After commission and refund reversals" : "Needs an approved configuration (Q8)"} />
              <StatCard label="Tax collected" value={s.ledger ? formatMoney(s.ledger.tax) : "Not available"} hint={s.ledger ? "Held for remittance; not revenue" : "Needs an approved configuration (Q7)"} />
              <StatCard label="Refunds processed" value={formatMoney(s.refunds.processed_paise)} hint={`${formatNumber(s.refunds.processed_count)} processed · ${s.refunds.in_flight_count} in progress · ${s.refunds.failed_count} failed`} tone="warning" />
            </section>
            <section className="grid gap-4 sm:grid-cols-3" aria-label="Commission">
              <StatCard label="Platform commission" value={s.commission ? formatMoney(s.commission.net_commission_paise) : "Not available"} hint={s.commission ? `${formatMoney(s.commission.commission_accrued_paise)} accrued − ${formatMoney(s.commission.commission_reversed_paise)} reversed · ${s.commission.bookings} bookings` : "Needs an approved configuration (Q7, Q8)"} tone="success" />
              <StatCard label="Commission reconciliation" value={s.commission ? (s.commission.reconciled ? "Reconciled" : "Differences found") : "Not available"} hint="Ledger against payment and refund records" tone={s.commission && !s.commission.reconciled ? "danger" : "primary"} />
              <div className="flex items-center"><Link href="/commission" className="text-sm text-primary hover:underline">Manage commission rules, history and reports →</Link></div>
            </section>
            <section className="grid gap-4 sm:grid-cols-3">
              <StatCard label="Rule in force" value={s.active_config ? `Version ${s.active_config.version}` : "None approved"} hint={s.active_config ? `Since ${formatDateTime(s.active_config.effective_from)}` : "No fee, tax or commission is applied anywhere"} tone={s.active_config ? "success" : "warning"} />
              <StatCard label="Captured payments in ledger" value={`${s.coverage.with_ledger_entry} of ${s.coverage.captured_payments}`} hint={s.coverage.without_ledger_entry ? `${s.coverage.without_ledger_entry} not in the ledger (before a rule was approved, or run “Update ledger”)` : "Complete for this period"} />
              <StatCard label="Owner payouts" value={s.payouts.enabled ? "Records enabled" : "Switched off"} hint="Automatic gateway payouts are not integrated." tone={s.payouts.enabled ? "success" : "warning"} />
            </section>
            <p className="text-xs text-muted-foreground">{s.payouts.note}</p>
          </>
        );
      })()}
    </div>
  );
}
