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
import { duration, formatDate, formatDateTime, formatMoney, titleCase } from "@/lib/format";
import { CommissionPanel } from "@/components/data/commission-panel";
import type { BookingDetail } from "@/lib/types";

export const metadata: Metadata = { title: "Booking" };

const CANCELLABLE = ["pending_payment", "payment_failed", "confirmed"];

export default async function BookingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [res, canCancel, canDispute] = await Promise.all([
    safe(adminGet<BookingDetail>(`/admin/bookings/${encodeURIComponent(id)}`)),
    hasPermission("bookings.manage"),
    hasPermission("disputes.manage"),
  ]);
  if (!res.ok) {
    if (res.error.status === 404 || res.error.status === 422) notFound();
    return <ErrorState message={`Could not load this booking (${res.error.message}).`} />;
  }
  const b = res.data;
  const back = [`/bookings/${b.id}`, "/bookings"];
  const activeDispute = b.disputes.find((d) => d.status === "open" || d.status === "investigating");
  const snap = b.price_snapshot ?? {};
  const n = (k: string) => Number((snap as Record<string, unknown>)[k] ?? 0);
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader
        title={b.booking_code}
        description="Status changes go through the booking rules; an administrator can cancel only in an exceptional case, with a reason."
        actions={<>
          <StatusBadge status={b.status} /><StatusBadge status={b.payment_status} />
          {canCancel && CANCELLABLE.includes(b.status) && (
            <ActionButton label="Cancel booking" title={`Cancel ${b.booking_code}`} path={`/admin/bookings/${b.id}/cancel`} danger fields={[REASON]} refresh={back} testId="booking-cancel"
              fixed={activeDispute ? { dispute_id: activeDispute.id } : {}}
              description={<>The slot is released and the customer and owner are told. {b.payment_status === "paid" ? <strong>No money moves: the payment stays captured until you decide on a refund separately.</strong> : "No payment had been taken."}</>} />
          )}
          {canDispute && !activeDispute && <ActionButton label="Open dispute" title="Open a dispute on this booking" path="/admin/disputes" fixed={{ booking_id: b.id }} refresh={[...back, "/disputes"]}
            fields={[{ name: "subject", label: "Subject", required: true, maxLength: 160 }, { name: "description", label: "What happened", type: "textarea", maxLength: 4000 },
              { name: "raised_by_role", label: "Raised by", type: "select", required: true, defaultValue: "customer", options: [{ value: "customer", label: "Customer" }, { value: "owner", label: "Owner" }, { value: "admin", label: "Admin (internal)" }] },
              { name: "priority", label: "Priority", type: "select", required: true, defaultValue: "normal", options: ["low", "normal", "high", "urgent"].map((v) => ({ value: v, label: titleCase(v) })) }]} testId="dispute-open" />}
        </>}
      />
      {b.refund_status === "awaiting" && <Alert variant="info" data-testid="refund-awaiting">This booking is cancelled and paid, and no refund has been decided. Open the payment to refund it (when refunds are enabled).</Alert>}
      {activeDispute && <Alert variant="info">Dispute in progress: <Link className="text-primary underline" href={`/disputes/${activeDispute.id}`}>{activeDispute.subject}</Link> ({titleCase(activeDispute.status)})</Alert>}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card><CardHeader><CardTitle>Customer</CardTitle></CardHeader><div className="space-y-1 px-6 pb-6 text-sm">
          <Link href={`/customers/${b.customer_id}`} className="font-medium text-primary hover:underline">{b.customer?.full_name ?? b.customer_name}</Link>
          <p>{b.customer?.email ?? "—"}</p><p>{b.customer?.phone ?? "—"}</p>{b.customer?.status && <StatusBadge status={b.customer.status} />}
        </div></Card>
        <Card><CardHeader><CardTitle>Owner</CardTitle></CardHeader><div className="space-y-1 px-6 pb-6 text-sm">
          <Link href={`/owners/${b.owner_id}`} className="font-medium text-primary hover:underline">{b.owner?.full_name ?? b.owner_name}</Link>
          <p>{b.owner?.business_name ?? "—"}</p><p>{b.owner?.email ?? "—"} · {b.owner?.phone ?? "—"}</p>{b.owner?.kyc_status && <StatusBadge status={b.owner.kyc_status} />}
        </div></Card>
        <Card><CardHeader><CardTitle>Venue</CardTitle></CardHeader><div className="space-y-1 px-6 pb-6 text-sm">
          <Link href={`/venues/${b.venue_id}`} className="font-medium text-primary hover:underline">{b.venue_name}</Link>
          <p>{b.venue?.address_line ?? "—"}{b.venue?.city ? `, ${b.venue.city}` : ""}</p><p>{b.venue?.contact_phone ?? "—"}</p>{b.venue && <StatusBadge status={b.venue.status} />}
        </div></Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Booking</CardTitle></CardHeader>
        <DetailGrid>
          <Detail label="Booking ID"><Mono>{b.id}</Mono></Detail>
          <Detail label="Sport">{b.sports.join(", ") || "—"}</Detail>
          <Detail label="Court / resource">{b.resource_name}</Detail>
          <Detail label="Date">{formatDate(b.booking_date)}</Detail>
          <Detail label="Slot">{b.local_start} – {b.local_end} ({duration(b.duration_minutes)})</Detail>
          <Detail label="City">{b.city}</Detail>
          <Detail label="Created">{formatDateTime(b.created_at)}</Detail>
          <Detail label="Cancelled">{b.cancelled_at ? `${formatDateTime(b.cancelled_at)}${b.cancel_reason ? ` — ${b.cancel_reason}` : ""}` : "—"}</Detail>
          <Detail label="Refund status">{b.refund_status === "none" ? "No refund" : <StatusBadge status={b.refund_status} />}{b.refunded_paise > 0 && ` · ${formatMoney(b.refunded_paise)} refunded`}</Detail>
        </DetailGrid>
      </Card>

      <Card data-testid="amount-breakdown">
        <CardHeader><CardTitle>Amount</CardTitle></CardHeader>
        <dl className="grid gap-2 px-6 pb-6 text-sm sm:max-w-md">
          {([["Slot price", n("base_amount_paise")], ["Platform fee", n("fees_paise")], ["Tax", n("tax_paise")], [`Discount${b.coupon?.code ? ` (${b.coupon.code})` : ""}`, -n("discount_paise")]] as const).map(([l, v]) => (
            <div key={l} className="flex justify-between"><dt className="text-muted-foreground">{l}</dt><dd className="tabular-nums">{formatMoney(v)}</dd></div>
          ))}
          <div className="flex justify-between border-t border-border pt-2 font-semibold"><dt>Total charged</dt><dd className="tabular-nums">{formatMoney(b.total_amount_paise, b.currency)}</dd></div>
        </dl>
      </Card>

      <CommissionPanel bookingId={b.id} />

      <Card>
        <CardHeader><CardTitle>Payment records</CardTitle></CardHeader>
        {b.payments.length === 0 ? <EmptyState title="No payment started" description="The customer has not opened checkout for this booking." /> : (
          <Table>
            <THead><TR><TH>Payment</TH><TH>Status</TH><TH className="text-right">Amount</TH><TH className="text-right">Refunded</TH><TH>Gateway reference</TH><TH>Created</TH></TR></THead>
            <TBody>{b.payments.map((p) => (
              <TR key={p.id}>
                <TD><Link href={`/payments/${p.id}`} className="font-medium text-primary hover:underline"><Mono>{p.id.slice(0, 8)}</Mono></Link></TD>
                <TD><StatusBadge status={p.status} /></TD>
                <TD className="text-right tabular-nums">{formatMoney(p.amount_paise, p.currency)}</TD>
                <TD className="text-right tabular-nums">{formatMoney(p.refunded_paise)}</TD>
                <TD><Mono>{p.razorpay_payment_id ?? p.razorpay_order_id}</Mono></TD>
                <TD>{formatDateTime(p.created_at)}</TD>
              </TR>
            ))}</TBody>
          </Table>
        )}
      </Card>

      {b.refunds.length > 0 && (
        <Card data-testid="booking-refunds">
          <CardHeader><CardTitle>Refunds</CardTitle></CardHeader>
          <Table>
            <THead><TR><TH>Refund</TH><TH className="text-right">Amount</TH><TH>Status</TH><TH>Reason</TH><TH>When</TH></TR></THead>
            <TBody>{b.refunds.map((r) => (
              <TR key={r.id}><TD><Link href={`/refunds/${r.id}`} className="text-primary hover:underline"><Mono>{r.id.slice(0, 8)}</Mono></Link></TD><TD className="text-right tabular-nums">{formatMoney(Number(r.amount_paise))}</TD><TD><StatusBadge status={String(r.status)} /></TD><TD className="max-w-xs truncate">{String(r.reason ?? "—")}</TD><TD className="text-xs">{formatDateTime(String(r.created_at))}</TD></TR>
            ))}</TBody>
          </Table>
        </Card>
      )}

      {b.disputes.length > 0 && (
        <Card><CardHeader><CardTitle>Disputes</CardTitle></CardHeader>
          <ul className="divide-y divide-border">{b.disputes.map((d) => (
            <li key={d.id} className="flex items-center justify-between gap-3 px-6 py-3 text-sm"><Link href={`/disputes/${d.id}`} className="font-medium text-primary hover:underline">{d.subject}</Link><StatusBadge status={d.status} /><span className="text-xs text-muted-foreground">{formatDateTime(d.created_at)}</span></li>
          ))}</ul>
        </Card>
      )}

      <Card data-testid="timeline">
        <CardHeader><CardTitle>Booking timeline</CardTitle></CardHeader>
        {b.timeline.length === 0 ? <EmptyState title="No history" /> : (
          <ol className="divide-y divide-border px-6 pb-2">
            {b.timeline.map((h, i) => (
              <li key={i} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
                <span>{h.from_status ? `${titleCase(h.from_status)} → ` : ""}<strong>{titleCase(h.to_status)}</strong> <span className="text-muted-foreground">by {h.actor_name ? `${h.actor_name} (${h.actor_role})` : h.actor_role}{h.reason ? ` · “${h.reason}”` : ""}</span></span>
                <span className="text-xs text-muted-foreground">{formatDateTime(h.created_at)}</span>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </div>
  );
}
