import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Detail, DetailGrid, Mono } from "@/components/data/detail";
import { PageHeader } from "@/components/data/page-header";
import { StatusBadge } from "@/components/data/status-badge";
import { Alert } from "@/components/ui/alert";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDateTime, formatMoney, titleCase } from "@/lib/format";
import type { PaymentDetail } from "@/lib/types";

export const metadata: Metadata = { title: "Payment" };

export default async function PaymentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const res = await safe(adminGet<PaymentDetail>(`/admin/payments/${encodeURIComponent(id)}`));
  if (!res.ok) {
    if (res.error.status === 404 || res.error.status === 422) notFound();
    return <ErrorState message={`Could not load this payment (${res.error.message}).`} />;
  }
  const p = res.data;
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader title={`Payment ${p.id.slice(0, 8)}`} description="Read-only gateway record. No card data is stored." actions={<StatusBadge status={p.status} />} />
      {p.review_required && <Alert data-testid="review-banner">Needs review: {p.review_reason ?? "flagged by the payment rules"}. No automatic refund is made (policy not approved).</Alert>}
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
