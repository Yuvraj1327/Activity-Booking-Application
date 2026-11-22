import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { BadgeCheck } from "lucide-react";
import { ActionButton, OPTIONAL_REASON, REASON } from "@/components/data/action-button";
import { BookingHistory } from "@/components/data/booking-history";
import { Detail, DetailGrid } from "@/components/data/detail";
import { PageHeader } from "@/components/data/page-header";
import { StatCard } from "@/components/data/stat-card";
import { StatusBadge } from "@/components/data/status-badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Alert } from "@/components/ui/alert";
import { buttonLink } from "@/components/ui/button-link";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { hasPermission } from "@/lib/admin-access";
import { formatDate, formatDateTime, formatMoney, titleCase } from "@/lib/format";
import type { SearchParams } from "@/lib/query";
import type { Row, VenueDetail } from "@/lib/types";

export const metadata: Metadata = { title: "Venue" };

type Hist = { id: string; action: string; from_status: string | null; to_status: string | null; reason: string | null; actor_role: string; actor_name: string | null; created_at: string };

export default async function VenuePage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<SearchParams> }) {
  const { id } = await params;
  const sp = await searchParams;
  const [res, hist, canModerate, reports] = await Promise.all([
    safe(adminGet<VenueDetail>(`/admin/venues/${encodeURIComponent(id)}`)),
    safe(adminGet<{ items: Hist[] }>(`/admin/venues/${encodeURIComponent(id)}/history`)),
    hasPermission("venues.moderate"),
    safe(adminGet<{ items: Row[] }>("/admin/venue-reports", { venue_id: id, limit: 5 })),
  ]);
  if (!res.ok) {
    if (res.error.status === 404 || res.error.status === 422) notFound();
    return <ErrorState message={`Could not load this venue (${res.error.message}).`} />;
  }
  const v = res.data;
  const back = [`/venues/${v.id}`, "/venues"];
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader
        title={v.name}
        description="Owners edit their own listings. Administrators approve, verify and suspend."
        actions={<>
          <StatusBadge status={v.status} />
          {v.is_verified && <span className="inline-flex items-center gap-1 text-sm text-primary" data-testid="verified"><BadgeCheck className="size-4" aria-hidden />Verified</span>}
          <Link className={buttonLink} href={`/bookings?venue_id=${v.id}`}>View bookings</Link>
        </>}
      />
      {v.status === "pending_review" && <Alert variant="info" data-testid="pending-note">Submitted {formatDateTime(v.submitted_at)} and waiting for approval. It is not visible to customers yet.</Alert>}
      {(v.status === "rejected" || v.status === "suspended") && v.status_reason && <Alert data-testid="reason-note">{titleCase(v.status)}: {v.status_reason}</Alert>}
      {v.status === "suspended" && v.future_confirmed_count > 0 && <Alert variant="info">{v.future_confirmed_count} upcoming confirmed booking(s) were NOT cancelled by the suspension. Handle them case by case from Bookings.</Alert>}

      {canModerate && (
        <Card><div className="flex flex-wrap items-center gap-2 p-4" data-testid="moderation-actions">
          <span className="mr-2 text-sm font-medium">Moderation</span>
          {v.status === "pending_review" && <>
            <ActionButton label="Approve" title="Approve and publish this venue?" path={`/admin/venues/${v.id}/approve`} fields={[OPTIONAL_REASON]} variant="default" refresh={back} testId="venue-approve" description="It becomes visible to customers immediately." success="Venue approved and published." />
            <ActionButton label="Reject" title="Reject this venue" path={`/admin/venues/${v.id}/reject`} fields={[REASON]} danger refresh={back} testId="venue-reject" description="The owner is told the reason and can fix and re-submit." />
          </>}
          {v.status === "published" && <ActionButton label="Suspend" title="Suspend this venue" path={`/admin/venues/${v.id}/suspend`} fields={[REASON]} danger refresh={back} testId="venue-suspend"
            description={<>It is hidden from customers and cannot take new bookings. Existing bookings are <strong>not</strong> cancelled or refunded ({v.future_confirmed_count} upcoming).</>} />}
          {v.status === "suspended" && <ActionButton label="Reinstate" title="Reinstate this venue?" path={`/admin/venues/${v.id}/reinstate`} fields={[OPTIONAL_REASON]} variant="default" refresh={back} testId="venue-reinstate" success="Venue reinstated." />}
          {["published", "pending_review", "suspended"].includes(v.status) && (v.is_verified
            ? <ActionButton label="Remove verification" path={`/admin/venues/${v.id}/unverify`} fields={[REASON]} refresh={back} />
            : <ActionButton label="Verify venue" title="Mark this venue as verified?" path={`/admin/venues/${v.id}/verify`} fields={[OPTIONAL_REASON]} refresh={back} testId="venue-verify" success="Venue verified." />)}
        </div></Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Bookings" value={String(v.bookings_count)} hint={`${v.confirmed_count} confirmed · ${v.completed_count} completed · ${v.cancelled_count} cancelled`} />
        <StatCard label="Gross paid" value={formatMoney(v.gross_paid_paise)} hint="Captured payments, before any deduction" />
        <StatCard label="Owner earnings" value={v.owner_earnings && v.owner_earnings.available ? formatMoney(v.owner_earnings.amount_paise) : "Not available"} hint={v.owner_earnings && !v.owner_earnings.available ? `Waiting for ${v.owner_earnings.depends_on}` : "Net of commission and refunds (ledger)"} />
        <StatCard label="Courts / resources" value={`${v.active_resources_count}/${v.resources_count}`} hint="active / total" />
      </div>

      <Card>
        <CardHeader><CardTitle>Listing</CardTitle></CardHeader>
        <DetailGrid>
          <Detail label="Owner"><Link href={`/owners/${v.owner_id}`} className="text-primary hover:underline">{v.owner_name}</Link> · {v.business_name} <StatusBadge status={v.owner_kyc_status ?? "not_submitted"} /></Detail>
          <Detail label="Categories">{v.categories.join(", ") || "—"}</Detail>
          <Detail label="City">{v.city}</Detail>
          <Detail label="Address">{v.address_line}</Detail>
          <Detail label="Venue phone">{v.contact_phone}</Detail>
          <Detail label="Time zone">{v.timezone}</Detail>
          <Detail label="Created">{formatDateTime(v.created_at)}</Detail>
          <Detail label="Published">{formatDateTime(v.published_at)}</Detail>
          <Detail label="Verified">{v.is_verified ? formatDateTime(v.verified_at) : "No"}</Detail>
          <Detail label="Rating">{v.rating_avg !== null ? `${v.rating_avg} (${v.rating_count})` : "No ratings yet"}</Detail>
          <div className="sm:col-span-2 lg:col-span-3"><Detail label="Description">{v.description}</Detail></div>
        </DetailGrid>
      </Card>

      <Card data-testid="performance">
        <CardHeader><CardTitle>Booking performance, last months</CardTitle></CardHeader>
        <Table>
          <THead><TR><TH>Month</TH><TH className="text-right">Bookings</TH><TH className="text-right">Completed</TH><TH className="text-right">Cancelled</TH><TH className="text-right">Gross paid</TH></TR></THead>
          <TBody>{v.performance.map((m) => <TR key={m.month}><TD>{formatDate(m.month).replace(/^\d+ /, "")}</TD><TD className="text-right tabular-nums">{m.bookings}</TD><TD className="text-right tabular-nums">{m.completed}</TD><TD className="text-right tabular-nums">{m.cancelled}</TD><TD className="text-right tabular-nums">{formatMoney(m.gross_paid_paise)}</TD></TR>)}</TBody>
        </Table>
      </Card>

      <Card id="reports">
        <CardHeader className="flex-row items-center justify-between"><CardTitle>Reports about this venue</CardTitle><Link href={`/venue-reports?venue_id=${v.id}`} className="text-sm text-primary hover:underline">All reports</Link></CardHeader>
        {!reports.ok || reports.data.items.length === 0 ? <EmptyState title="No reports" /> : (
          <ul className="divide-y divide-border">{reports.data.items.map((r) => (
            <li key={r.id} className="flex items-center justify-between gap-3 px-6 py-3 text-sm"><Link href={`/venue-reports/${r.id}`} className="font-medium text-primary hover:underline">{titleCase(String(r.reason))}</Link><StatusBadge status={String(r.status)} /><span className="text-xs text-muted-foreground">{formatDateTime(String(r.created_at))}</span></li>
          ))}</ul>
        )}
      </Card>

      <Card id="history">
        <CardHeader><CardTitle>Approval, verification and suspension history</CardTitle></CardHeader>
        {!hist.ok || hist.data.items.length === 0 ? <EmptyState title="No moderation events yet" /> : (
          <ol className="divide-y divide-border">{hist.data.items.map((h) => (
            <li key={h.id} className="flex flex-wrap items-start justify-between gap-2 px-6 py-3 text-sm">
              <div><p className="font-medium">{titleCase(h.action)}{h.from_status && h.to_status && h.from_status !== h.to_status && <span className="font-normal text-muted-foreground"> · {titleCase(h.from_status)} → {titleCase(h.to_status)}</span>}</p>{h.reason && <p className="text-muted-foreground">“{h.reason}”</p>}</div>
              <p className="text-xs text-muted-foreground">{h.actor_name ?? h.actor_role} ({h.actor_role}) · {formatDateTime(h.created_at)}</p>
            </li>
          ))}</ol>
        )}
      </Card>

      <BookingHistory filter="venue_id" id={v.id} path={`/venues/${v.id}`} params={sp} title="Booking history" />
    </div>
  );
}
