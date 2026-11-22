import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ActionButton, REASON } from "@/components/data/action-button";
import { Detail, DetailGrid, Mono } from "@/components/data/detail";
import { PageHeader } from "@/components/data/page-header";
import { StatusBadge } from "@/components/data/status-badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Alert } from "@/components/ui/alert";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { hasPermission } from "@/lib/admin-access";
import { formatDateTime, formatMoney, titleCase } from "@/lib/format";
import type { PaymentDetail } from "@/lib/types";

export const metadata: Metadata = { title: "Payment" };

type Avail = { enabled: boolean; reason: string | null; remaining_paise: number; mode: string };

export default async function PaymentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [res, canRefund] = await Promise.all([safe(adminGet<PaymentDetail & { refund_availability: Avail | null }>(`/admin/payments/${encodeURIComponent(id)}`)), hasPermission("refunds.manage")]);
  if (!res.ok) {
    if (res.error.status === 404 || res.error.status === 422) notFound();
    return <ErrorState message={`Could not load this payment (${res.error.message}).`} />;
  }
  const p = res.data;
  const av = p.refund_availability;
  const back = [`/payments/${p.id}`, "/payments", "/refunds", `/bookings/${p.booking_id}`];
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader title={`Payment ${p.id.slice(0, 8)}`} description="Gateway record. No card data is stored." actions={<StatusBadge status={p.status} />} />
      {p.review_required && <Alert data-testid="review-banner">Needs review: {p.review_reason ?? "flagged by the payment rules"}. No automatic refund is made.</Alert>}

      <Card data-testid="refund-panel">
        <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
          <div><CardTitle>Refunds</CardTitle><p className="mt-1 text-sm text-muted-foreground">Refunded {formatMoney(p.refunded_paise)} · in progress {formatMoney(p.refund_in_flight_paise)} · refundable now {av ? formatMoney(av.remaining_paise) : "—"}</p></div>
          {canRefund && av && (
            <div className="flex gap-2">
              <ActionButton
                label="Refund…" title="Refund this payment" path={`/admin/payments/${p.id}/refunds`} idempotent variant="default" refresh={back} testId="refund-open"
                disabled={!av.enabled} disabledReason={av.reason ?? undefined}
                success="Refund sent to Razorpay. Its status updates when the gateway confirms."
                description={<>Money is returned to the customer through Razorpay ({av.mode} mode). This cannot be undone. Leave the amount empty to refund the whole remaining {formatMoney(av.remaining_paise)}. A full refund needs the booking to be cancelled first.</>}
                fields={[{ name: "amount_paise", label: "Amount (₹)", type: "money", placeholder: `Up to ${(av.remaining_paise / 100).toFixed(2)}`, help: "Empty = refund everything that is left." }, REASON]}
              />
            </div>
          )}
        </CardHeader>
        {av && !av.enabled && <p className="px-6 pb-4 text-sm text-muted-foreground" data-testid="refund-blocked">Refunds cannot be started: {av.reason}</p>}
        {p.refunds.length === 0 ? <EmptyState title="No refunds on this payment" /> : (
          <Table>
            <THead><TR><TH>Refund</TH><TH className="text-right">Amount</TH><TH>Status</TH><TH>Source</TH><TH>Reason</TH><TH>When</TH></TR></THead>
            <TBody>{p.refunds.map((r) => (
              <TR key={r.id}>
                <TD><Link href={`/refunds/${r.id}`} className="text-primary hover:underline"><Mono>{r.id.slice(0, 8)}</Mono></Link></TD>
                <TD className="text-right tabular-nums">{formatMoney(Number(r.amount_paise))}</TD>
                <TD><StatusBadge status={String(r.status)} />{r.failure_reason ? <p className="mt-1 max-w-xs text-xs text-muted-foreground">{String(r.failure_reason)}</p> : null}</TD>
                <TD>{titleCase(String(r.source))}</TD><TD className="max-w-xs truncate">{String(r.reason ?? "—")}</TD><TD className="text-xs">{formatDateTime(String(r.created_at))}</TD>
              </TR>
            ))}</TBody>
          </Table>
        )}
      </Card>

      <Card>
        <CardHeader><CardTitle>Transaction</CardTitle></CardHeader>
        <DetailGrid>
          <Detail label="Payment ID"><Mono>{p.id}</Mono></Detail>
          <Detail label="Booking"><Link href={`/bookings/${p.booking_id}`} className="text-primary hover:underline">{p.booking_code}</Link> <StatusBadge status={p.booking_status} /></Detail>
          <Detail label="Venue">{p.venue_name}</Detail>
          <Detail label="Customer"><Link href={`/customers/${p.customer_id}`} className="text-primary hover:underline">View customer</Link></Detail>
          <Detail label="Amount">{formatMoney(p.amount_paise, p.currency)} <span className="text-muted-foreground">({p.currency}, gross)</span></Detail>
          <Detail label="Method">{p.method}</Detail>
          <Detail label="Razorpay order"><Mono>{p.razorpay_order_id}</Mono></Detail>
          <Detail label="Razorpay payment"><Mono>{p.razorpay_payment_id ?? "—"}</Mono></Detail>
          <Detail label="Created">{formatDateTime(p.created_at)}</Detail>
          <Detail label="Captured">{formatDateTime(p.captured_at)}</Detail>
          <Detail label="Failed">{p.failed_at ? `${formatDateTime(p.failed_at)} — ${p.failure_reason ?? p.failure_code ?? ""}` : "—"}</Detail>
        </DetailGrid>
      </Card>
      <Card>
        <CardHeader><CardTitle>Gateway events</CardTitle></CardHeader>
        {p.events.length === 0 ? <EmptyState title="No events yet" /> : (
          <Table>
            <THead><TR><TH>Event</TH><TH>Source</TH><TH>Outcome</TH><TH>Event ID</TH><TH>When</TH></TR></THead>
            <TBody>{p.events.map((e) => (
              <TR key={e.id}><TD>{e.event_type}</TD><TD>{titleCase(e.source)}</TD><TD>{titleCase(e.outcome)}</TD><TD><Mono>{e.provider_event_id ?? "—"}</Mono></TD><TD>{formatDateTime(e.created_at)}</TD></TR>
            ))}</TBody>
          </Table>
        )}
      </Card>
    </div>
  );
}
