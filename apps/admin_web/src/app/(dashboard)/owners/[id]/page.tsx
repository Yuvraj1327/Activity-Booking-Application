import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { BriefBookings } from "@/components/data/booking-table";
import { Detail, DetailGrid } from "@/components/data/detail";
import { PageHeader } from "@/components/data/page-header";
import { StatCard } from "@/components/data/stat-card";
import { StatusBadge } from "@/components/data/status-badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { StatusControl } from "@/components/data/status-control";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDate, formatDateTime, formatMoney } from "@/lib/format";
import type { OwnerDetail } from "@/lib/types";

export const metadata: Metadata = { title: "Owner" };

export default async function OwnerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const res = await safe(adminGet<OwnerDetail>(`/admin/owners/${encodeURIComponent(id)}`));
  if (!res.ok) {
    if (res.error.status === 404 || res.error.status === 422) notFound();
    return <ErrorState message={`Could not load this owner (${res.error.message}).`} />;
  }
  const o = res.data;
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader title={o.full_name} description={o.business_name} actions={<><StatusBadge status={o.status} /><StatusControl role="owner" id={o.id} name={o.full_name} status={o.status} /></>} />
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Venues" value={String(o.venues.length)} />
        <StatCard label="Bookings" value={String(o.bookings_count)} hint={`${o.confirmed_count} confirmed`} />
        <StatCard label="Gross paid" value={formatMoney(o.gross_paid_paise)} hint="Captured payments, before any deduction" />
      </div>
      <Card>
        <CardHeader><CardTitle>Profile and contact</CardTitle></CardHeader>
        <DetailGrid>
          <Detail label="E-mail">{o.email}</Detail>
          <Detail label="Phone">{o.phone}</Detail>
          <Detail label="Registered">{formatDateTime(o.created_at)}</Detail>
          <Detail label="Business phone">{o.business_phone}</Detail>
          <Detail label="Business e-mail">{o.business_email}</Detail>
          <Detail label="Business address">{o.business_address}</Detail>
        </DetailGrid>
      </Card>
      <Card>
        <CardHeader><CardTitle>Venues (read-only)</CardTitle></CardHeader>
        {o.venues.length === 0 ? <EmptyState title="No venues yet" /> : (
          <Table>
            <THead><TR><TH>Venue</TH><TH>City</TH><TH>Status</TH><TH className="text-right">Bookings</TH><TH>Created</TH></TR></THead>
            <TBody>{o.venues.map((v) => (
              <TR key={v.id}>
                <TD><Link href={`/venues/${v.id}`} className="font-medium text-primary hover:underline">{v.name}</Link></TD>
                <TD>{v.city ?? "—"}</TD><TD><StatusBadge status={v.status} /></TD>
                <TD className="text-right tabular-nums">{v.confirmed_count}/{v.bookings_count}</TD><TD>{formatDate(v.created_at)}</TD>
              </TR>
            ))}</TBody>
          </Table>
        )}
      </Card>
      <Card>
        <CardHeader><CardTitle>Recent booking activity</CardTitle></CardHeader>
        {o.recent_bookings.length === 0 ? <EmptyState title="No bookings yet" /> : <BriefBookings items={o.recent_bookings} />}
      </Card>
    </div>
  );
}
