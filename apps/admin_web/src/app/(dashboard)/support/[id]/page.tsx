import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ActionButton } from "@/components/data/action-button";
import { Detail, DetailGrid } from "@/components/data/detail";
import { PageHeader } from "@/components/data/page-header";
import { StatusBadge } from "@/components/data/status-badge";
import { ErrorState } from "@/components/data/states";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDate, formatDateTime, formatMoney, titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Support ticket" };

type Ticket = {
  id: string; kind: string; subject: string; message: string; status: string; priority: string; platform: string | null; app_version: string | null; created_at: string; resolved_at: string | null; assignee_name: string | null;
  customer: { id: string; full_name: string; email: string | null; phone: string | null; role: string; status: string } | null;
  booking: { id: string; booking_code: string; status: string; payment_status: string; venue_name: string; booking_date: string; total_amount_paise: number } | null;
  messages: { id: string; kind: "reply" | "note" | "event"; body: string; author_role: string; author_name: string | null; created_at: string }[];
};

export default async function TicketPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const res = await safe(adminGet<Ticket>(`/admin/support/tickets/${encodeURIComponent(id)}`));
  if (!res.ok) {
    if (res.error.status === 404 || res.error.status === 422) notFound();
    return <ErrorState message={`Could not load this ticket (${res.error.message}).`} />;
  }
  const t = res.data;
  const back = [`/support/${t.id}`, "/support"];
  const closed = t.status === "resolved" || t.status === "closed";
  const c = t.customer;
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader title={t.subject} description={`${titleCase(t.kind)} · received ${formatDateTime(t.created_at)}`} actions={<><StatusBadge status={t.priority} /><StatusBadge status={t.status} /></>} />
      <Card><div className="flex flex-wrap gap-2 p-4" data-testid="ticket-actions">
        {!closed && <ActionButton label="Reply to customer" title="Reply to the customer" path={`/admin/support/tickets/${t.id}/messages`} variant="default" refresh={back} testId="ticket-reply" description="They get a notification and can read this in the app." fields={[{ name: "body", label: "Message", type: "textarea", required: true }]} fixed={{ internal: false }} />}
        <ActionButton label="Internal note" title="Add an internal note" path={`/admin/support/tickets/${t.id}/messages`} fixed={{ internal: true }} refresh={back} description="Only administrators see this." fields={[{ name: "body", label: "Note", type: "textarea", required: true }]} />
        <ActionButton label="Status & priority" path={`/admin/support/tickets/${t.id}`} method="PATCH" refresh={back} testId="ticket-update"
          fields={[{ name: "status", label: "Status", type: "select", defaultValue: t.status, options: ["open", "in_progress", "resolved", "closed"].map((v) => ({ value: v, label: titleCase(v) })) },
            { name: "priority", label: "Priority", type: "select", defaultValue: t.priority, options: ["low", "normal", "high", "urgent"].map((v) => ({ value: v, label: titleCase(v) })) },
            { name: "assigned_to_me", label: "Assign to me", type: "checkbox", defaultValue: false }]} />
        <ActionButton label={t.booking ? "Change booking link" : "Link a booking"} path={`/admin/support/tickets/${t.id}`} method="PATCH" refresh={back}
          fields={[{ name: "booking_id", label: "Booking ID", placeholder: "Paste the booking id (from the booking page)", emptyAsNull: true }]} />
      </div></Card>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card><CardHeader><CardTitle>Customer</CardTitle></CardHeader><DetailGrid>
          <Detail label="Name">{c ? <Link href={c.role === "owner" ? `/owners/${c.id}` : `/customers/${c.id}`} className="text-primary hover:underline">{c.full_name}</Link> : "—"}</Detail>
          <Detail label="Role">{c ? titleCase(c.role) : "—"}</Detail><Detail label="E-mail">{c?.email}</Detail><Detail label="Phone">{c?.phone}</Detail>
          <Detail label="App">{[t.platform, t.app_version].filter(Boolean).join(" ") || "—"}</Detail><Detail label="Assigned to">{t.assignee_name}</Detail>
        </DetailGrid></Card>
        <Card><CardHeader><CardTitle>Related booking</CardTitle></CardHeader>
          {t.booking ? <DetailGrid>
            <Detail label="Booking"><Link href={`/bookings/${t.booking.id}`} className="text-primary hover:underline">{t.booking.booking_code}</Link></Detail><Detail label="Venue">{t.booking.venue_name}</Detail>
            <Detail label="Date">{formatDate(t.booking.booking_date)}</Detail><Detail label="Amount">{formatMoney(t.booking.total_amount_paise)}</Detail>
            <Detail label="Status"><StatusBadge status={t.booking.status} /></Detail><Detail label="Payment"><StatusBadge status={t.booking.payment_status} /></Detail>
          </DetailGrid> : <p className="px-6 pb-6 text-sm text-muted-foreground">No booking linked. The apps do not attach one, so link it if the message is about a booking.</p>}
        </Card>
      </div>
      <Card data-testid="ticket-thread">
        <CardHeader><CardTitle>Conversation and history</CardTitle></CardHeader>
        <ol className="space-y-3 px-6 pb-6">
          <li className="rounded-lg border border-border bg-muted/40 p-4 text-sm"><p className="mb-1 text-xs text-muted-foreground">{c?.full_name ?? "Customer"} · {formatDateTime(t.created_at)}</p><p className="whitespace-pre-wrap">{t.message}</p></li>
          {t.messages.map((m) => (
            <li key={m.id} className={cn("rounded-lg border p-4 text-sm", m.kind === "reply" && "border-primary/30 bg-primary-tint/50", m.kind === "note" && "border-warning/40 bg-warning/10", m.kind === "event" && "border-dashed text-muted-foreground")}>
              <p className="mb-1 text-xs text-muted-foreground">{m.kind === "event" ? "History" : m.kind === "note" ? "Internal note" : "Reply to customer"} · {m.author_name ?? m.author_role} · {formatDateTime(m.created_at)}</p>
              <p className="whitespace-pre-wrap">{m.body}</p>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
