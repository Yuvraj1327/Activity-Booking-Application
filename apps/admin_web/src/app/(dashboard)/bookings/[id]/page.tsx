import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Detail, DetailGrid, Mono } from "@/components/data/detail";
import { PageHeader } from "@/components/data/page-header";
import { StatusBadge } from "@/components/data/status-badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { duration, formatDate, formatDateTime, formatMoney, titleCase } from "@/lib/format";
import type { BookingDetail } from "@/lib/types";

export const metadata: Metadata = { title: "Booking" };

export default async function BookingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const res = await safe(adminGet<BookingDetail>(`/admin/bookings/${encodeURIComponent(id)}`));
  if (!res.ok) {
    if (res.error.status === 404 || res.error.status === 422) notFound();
    return <ErrorState message={`Could not load this booking (${res.error.message}).`} />;
  }
  const b = res.data;
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader title={b.booking_code} description="Read-only. Booking status changes follow the booking rules, not the admin console." actions={<><StatusBadge status={b.status} /><StatusBadge status={b.payment_status} /></>} />
      <Card>
        <CardHeader><CardTitle>Booking</CardTitle></CardHeader>
        <DetailGrid>
          <Detail label="Booking ID"><Mono>{b.id}</Mono></Detail>
          <Detail label="Customer"><Link href={`/customers/${b.customer_id}`} className="text-primary hover:underline">{b.customer_name}</Link></Detail>
          <Detail label="Owner"><Link href={`/owners/${b.owner_id}`} className="text-primary hover:underline">{b.owner_name}</Link></Detail>
          <Detail label="Venue"><Link href={`/venues/${b.venue_id}`} className="text-primary hover:underline">{b.venue_name}</Link> · {b.resource_name}</Detail>
          <Detail label="Date">{formatDate(b.booking_date)}</Detail>
          <Detail label="Time">{b.local_start} – {b.local_end} ({duration(b.duration_minutes)})</Detail>
          <Detail label="Amount">{formatMoney(b.total_amount_paise, b.currency)}</Detail>
          <Detail label="Created">{formatDateTime(b.created_at)}</Detail>
          <Detail label="Cancelled">{b.cancelled_at ? `${formatDateTime(b.cancelled_at)}${b.cancel_reason ? ` — ${b.cancel_reason}` : ""}` : "—"}</Detail>
        </DetailGrid>
      </Card>
      <Card>
        <CardHeader><CardTitle>Payment records</CardTitle></CardHeader>
        {b.payments.length === 0 ? <EmptyState title="No payment started" description="The customer has not opened checkout for this booking." /> : (
          <Table>
            <THead><TR><TH>Payment</TH><TH>Status</TH><TH className="text-right">Amount</TH><TH>Gateway reference</TH><TH>Created</TH></TR></THead>
            <TBody>{b.payments.map((p) => (
              <TR key={p.id}>
                <TD><Link href={`/payments/${p.id}`} className="font-medium text-primary hover:underline"><Mono>{p.id.slice(0, 8)}</Mono></Link></TD>
                <TD><StatusBadge status={p.status} /></TD>
                <TD className="text-right tabular-nums">{formatMoney(p.amount_paise, p.currency)}</TD>
                <TD><Mono>{p.razorpay_payment_id ?? p.razorpay_order_id}</Mono></TD>
                <TD>{formatDateTime(p.created_at)}</TD>
              </TR>
            ))}</TBody>
          </Table>
        )}
      </Card>
      <Card>
        <CardHeader><CardTitle>Status history</CardTitle></CardHeader>
        {b.history.length === 0 ? <EmptyState title="No history" /> : (
          <ol className="divide-y divide-border px-6 pb-2">
            {b.history.map((h, i) => (
              <li key={i} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
                <span>{h.from_status ? `${titleCase(h.from_status)} → ` : ""}<strong>{titleCase(h.to_status)}</strong> <span className="text-muted-foreground">by {h.actor_role}{h.reason ? ` · ${h.reason}` : ""}</span></span>
                <span className="text-xs text-muted-foreground">{formatDateTime(h.created_at)}</span>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </div>
  );
}
