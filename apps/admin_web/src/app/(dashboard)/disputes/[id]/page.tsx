import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ActionButton } from "@/components/data/action-button";
import { Detail, DetailGrid } from "@/components/data/detail";
import { PageHeader } from "@/components/data/page-header";
import { StatusBadge } from "@/components/data/status-badge";
import { ErrorState } from "@/components/data/states";
import { Alert } from "@/components/ui/alert";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDate, formatDateTime, formatMoney, titleCase } from "@/lib/format";

export const metadata: Metadata = { title: "Dispute" };

type Dispute = {
  id: string; booking_id: string; booking_code: string; venue_name: string; customer_name: string; payment_id: string | null; raised_by_role: string;
  subject: string; description: string | null; status: string; priority: string; resolution_type: string | null; resolution_note: string | null; resolved_at: string | null;
  booking: { status: string; payment_status: string; total_amount_paise: number; currency: string; booking_date: string };
  payment: { id: string; status: string; amount_paise: number; razorpay_payment_id: string | null } | null;
  refunds: { id: string; amount_paise: number; status: string; created_at: string }[];
  events: { id: string; kind: string; body: string | null; data: Record<string, unknown>; actor_role: string; actor_name: string | null; created_at: string }[];
};

export default async function DisputePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const res = await safe(adminGet<Dispute>(`/admin/disputes/${encodeURIComponent(id)}`));
  if (!res.ok) {
    if (res.error.status === 404 || res.error.status === 422) notFound();
    return <ErrorState message={`Could not load this dispute (${res.error.message}).`} />;
  }
  const d = res.data;
  const active = d.status === "open" || d.status === "investigating";
  const back = [`/disputes/${d.id}`, "/disputes"];
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader title={d.subject} description={`${d.booking_code} · ${d.venue_name} · ${d.customer_name}`} actions={<><StatusBadge status={d.priority} /><StatusBadge status={d.status} /></>} />
      {active && (
        <Card><div className="flex flex-wrap gap-2 p-4" data-testid="dispute-actions">
          <ActionButton label="Add note" title="Add an admin note" path={`/admin/disputes/${d.id}/events`} fixed={{ kind: "note" }} fields={[{ name: "body", label: "Note", type: "textarea", required: true }]} refresh={back} />
          <ActionButton label="Add evidence" title="Record evidence" path={`/admin/disputes/${d.id}/events`} fixed={{ kind: "evidence" }} fields={[{ name: "body", label: "Evidence", type: "textarea", required: true, help: "Describe what you received and from whom (e.g. owner's photos by e-mail, call with the venue)." }]} refresh={back} />
          <ActionButton label="Update status / priority" path={`/admin/disputes/${d.id}`} method="PATCH" refresh={back}
            fields={[{ name: "status", label: "Status", type: "select", defaultValue: d.status, options: [{ value: "open", label: "Open" }, { value: "investigating", label: "Investigating" }] },
              { name: "priority", label: "Priority", type: "select", defaultValue: d.priority, options: ["low", "normal", "high", "urgent"].map((v) => ({ value: v, label: titleCase(v) })) },
              { name: "reason", label: "Note (optional)", type: "textarea", maxLength: 300 }]} />
          <ActionButton label="Resolve…" title="Resolve this dispute" path={`/admin/disputes/${d.id}/resolve`} variant="default" refresh={back} testId="dispute-resolve"
            description="A resolution can only claim something that has actually happened: choose a refund outcome only after the refund has been accepted, and cancelled only after the booking is cancelled."
            fields={[{ name: "outcome", label: "Outcome", type: "select", required: true, defaultValue: "resolved", options: [{ value: "resolved", label: "Resolved" }, { value: "rejected", label: "Rejected (no merit)" }] },
              { name: "resolution_type", label: "What was done", type: "select", required: true, options: [{ value: "no_action", label: "No action needed" }, { value: "refund_full", label: "Full refund issued" }, { value: "refund_partial", label: "Partial refund issued" }, { value: "booking_cancelled", label: "Booking cancelled" }, { value: "other", label: "Other" }] },
              { name: "resolution_note", label: "Resolution details", type: "textarea", required: true, maxLength: 300 }]} />
          <Link className="inline-flex h-8 items-center rounded-md border border-border px-3 text-sm hover:bg-muted" href={`/bookings/${d.booking_id}`}>Go to booking (cancel / refund)</Link>
        </div></Card>
      )}
      {!active && <Alert variant="info" data-testid="resolution">{titleCase(d.status)} on {formatDateTime(d.resolved_at)} · {titleCase(d.resolution_type ?? "")}: {d.resolution_note}</Alert>}
      <Card>
        <CardHeader><CardTitle>Booking and payment</CardTitle></CardHeader>
        <DetailGrid>
          <Detail label="Booking"><Link href={`/bookings/${d.booking_id}`} className="text-primary hover:underline">{d.booking_code}</Link> <StatusBadge status={d.booking.status} /></Detail>
          <Detail label="Date">{formatDate(d.booking.booking_date)}</Detail>
          <Detail label="Amount">{formatMoney(d.booking.total_amount_paise, d.booking.currency)} · <StatusBadge status={d.booking.payment_status} /></Detail>
          <Detail label="Payment">{d.payment ? <Link href={`/payments/${d.payment.id}`} className="text-primary hover:underline">{d.payment.razorpay_payment_id ?? d.payment.id.slice(0, 8)} ({titleCase(d.payment.status)})</Link> : "No payment"}</Detail>
          <Detail label="Refunds">{d.refunds.length ? d.refunds.map((r) => <span key={r.id} className="mr-2"><Link href={`/refunds/${r.id}`} className="text-primary hover:underline">{formatMoney(r.amount_paise)}</Link> <StatusBadge status={r.status} /></span>) : "None linked"}</Detail>
          <Detail label="Raised by">{titleCase(d.raised_by_role)}</Detail>
          <div className="sm:col-span-2 lg:col-span-3"><Detail label="Description">{d.description}</Detail></div>
        </DetailGrid>
      </Card>
      <Card data-testid="dispute-history">
        <CardHeader><CardTitle>Resolution and action history</CardTitle></CardHeader>
        <ol className="divide-y divide-border">{d.events.map((e) => (
          <li key={e.id} className="px-6 py-3 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">{titleCase(e.kind)}</span><span className="text-xs text-muted-foreground">{e.actor_name ?? e.actor_role} · {formatDateTime(e.created_at)}</span></div>
            {e.body && <p className="mt-1 whitespace-pre-wrap text-muted-foreground">{e.body}</p>}
            {(e.data.from || e.data.to) ? <p className="mt-1 text-xs text-muted-foreground">{String(e.data.from)} → {String(e.data.to)}</p> : null}
          </li>
        ))}</ol>
      </Card>
    </div>
  );
}
