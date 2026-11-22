import type { Metadata } from "next";
import Link from "next/link";
import { CheckCircle2, Clock, ShieldAlert, XCircle } from "lucide-react";
import { ExportButton } from "@/components/data/export-button";
import { FilterBar } from "@/components/data/filter-bar";
import { Mono } from "@/components/data/detail";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { StatCard } from "@/components/data/stat-card";
import { StatusBadge } from "@/components/data/status-badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDateTime, formatMoney, formatNumber, PAYMENT_STATUSES } from "@/lib/format";
import { one, PAGE_SIZE, pageOf, type SearchParams } from "@/lib/query";
import type { Paged, PaymentRow, PaymentSummary } from "@/lib/types";

export const metadata: Metadata = { title: "Payments" };

export default async function PaymentsPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const { offset, page } = pageOf(params);
  const f = { q: one(params, "q"), status: one(params, "status"), from: one(params, "from"), to: one(params, "to"), review_required: one(params, "review") === "1" ? "true" : undefined, venue_id: one(params, "venue_id"), refund_status: one(params, "refund_status") };
  const [list, summary] = await Promise.all([
    safe(adminGet<Paged<PaymentRow>>("/admin/payments", { ...f, limit: PAGE_SIZE, offset })),
    safe(adminGet<PaymentSummary>("/admin/payments/summary")),
  ]);
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader title="Payments & transactions" description="Recorded Razorpay transactions with their refunds. Amounts are gross." actions={<ExportButton kind="payments" query={{ status: f.status, from: f.from, to: f.to }} />} />
      {summary.ok ? (
        <>
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Payment totals (all time)">
            <StatCard label="Successful payments" value={formatMoney(summary.data.gross_captured_paise)} hint={`${formatNumber(summary.data.captured_count)} transactions · gross`} icon={CheckCircle2} tone="success" />
            <StatCard label="Failed" value={formatNumber(summary.data.failed_count)} icon={XCircle} tone="danger" />
            <StatCard label="Pending / open" value={formatNumber(summary.data.open_count)} icon={Clock} tone="warning" />
            <StatCard label="Need review" value={formatNumber(summary.data.review_required_count)} hint="Paid after the hold ended, etc." icon={ShieldAlert} tone="danger" />
          </section>
          <p className="text-sm text-muted-foreground" data-testid="refund-summary">
            Refunds: {formatMoney(summary.data.refunds.processed_paise)} processed ({summary.data.refunds.processed_count}) · {summary.data.refunds.in_flight_count} in progress · {summary.data.refunds.failed_count} failed. <Link href="/refunds" className="text-primary hover:underline">Open refund history</Link>
          </p>
        </>
      ) : <ErrorState message={`Could not load payment totals (${summary.error.message}).`} />}
      <Card>
        <FilterBar path="/payments" params={params} fields={[
          { kind: "search", name: "q", placeholder: "Booking ID, payment ID or gateway reference" },
          { kind: "select", name: "status", label: "Status", options: PAYMENT_STATUSES },
          { kind: "select", name: "review", label: "Review", options: [{ value: "1", label: "Needs review" }] },
          { kind: "select", name: "refund_status", label: "Refund", options: [{ value: "none", label: "No refund" }, { value: "pending", label: "In progress" }, { value: "processed", label: "Processed" }, { value: "failed", label: "Failed" }, { value: "uncertain", label: "Result unknown" }] },
          { kind: "date", name: "from", label: "Created from" },
          { kind: "date", name: "to", label: "to" },
        ]} />
        {!list.ok ? <div className="p-4"><ErrorState message={`Could not load payments (${list.error.message}).`} /></div> : list.data.items.length === 0 ? (
          <EmptyState title="No payments found" description="Payments appear here once customers start checkout." />
        ) : (
          <>
            <Table>
              <THead><TR><TH>Payment</TH><TH>Booking</TH><TH>Venue</TH><TH className="text-right">Amount</TH><TH>Method</TH><TH>Status</TH><TH className="text-right">Refunded</TH><TH>Gateway reference</TH><TH>Date</TH></TR></THead>
              <TBody>
                {list.data.items.map((p) => (
                  <TR key={p.id}>
                    <TD><Link href={`/payments/${p.id}`} className="font-medium text-primary hover:underline"><Mono>{p.id.slice(0, 8)}</Mono></Link></TD>
                    <TD><Link href={`/bookings/${p.booking_id}`} className="hover:underline">{p.booking_code}</Link></TD>
                    <TD>{p.venue_name}</TD>
                    <TD className="text-right tabular-nums">{formatMoney(p.amount_paise, p.currency)} <span className="text-xs text-muted-foreground">{p.currency}</span></TD>
                    <TD>{p.method ?? "—"}</TD>
                    <TD><div className="flex items-center gap-1"><StatusBadge status={p.status} />{p.review_required && <Badge tone="danger">Review</Badge>}</div></TD>
                    <TD className="text-right tabular-nums">{p.refunded_paise ? formatMoney(p.refunded_paise) : p.refund_in_flight_paise ? <span className="text-muted-foreground">{formatMoney(p.refund_in_flight_paise)} pending</span> : "—"}</TD>
                    <TD><Mono>{p.razorpay_payment_id ?? p.razorpay_order_id}</Mono></TD>
                    <TD className="whitespace-nowrap text-xs text-muted-foreground">{formatDateTime(p.created_at)}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
            <Pagination path="/payments" params={params} page={page} hasMore={list.data.has_more} shown={list.data.items.length} />
          </>
        )}
      </Card>
    </div>
  );
}
