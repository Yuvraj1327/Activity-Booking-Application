import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Detail, DetailGrid } from "@/components/data/detail";
import { PageHeader } from "@/components/data/page-header";
import { StatCard } from "@/components/data/stat-card";
import { StatusBadge } from "@/components/data/status-badge";
import { ErrorState } from "@/components/data/states";
import { buttonLink } from "@/components/ui/button-link";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDateTime, formatMoney } from "@/lib/format";
import type { VenueDetail } from "@/lib/types";

export const metadata: Metadata = { title: "Venue" };

export default async function VenuePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const res = await safe(adminGet<VenueDetail>(`/admin/venues/${encodeURIComponent(id)}`));
  if (!res.ok) {
    if (res.error.status === 404 || res.error.status === 422) notFound();
    return <ErrorState message={`Could not load this venue (${res.error.message}).`} />;
  }
  const v = res.data;
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader title={v.name} description="Read-only. The owner manages this listing." actions={<><StatusBadge status={v.status} /><Link className={buttonLink} href={`/bookings?venue_id=${v.id}`}>View bookings</Link></>} />
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Bookings" value={String(v.bookings_count)} hint={`${v.confirmed_count} confirmed`} />
        <StatCard label="Gross paid" value={formatMoney(v.gross_paid_paise)} />
        <StatCard label="Courts / resources" value={`${v.active_resources_count}/${v.resources_count}`} hint="active / total" />
      </div>
      <Card>
        <CardHeader><CardTitle>Listing</CardTitle></CardHeader>
        <DetailGrid>
          <Detail label="Owner"><Link href={`/owners/${v.owner_id}`} className="text-primary hover:underline">{v.owner_name}</Link> · {v.business_name}</Detail>
          <Detail label="Categories">{v.categories.join(", ") || "—"}</Detail>
          <Detail label="City">{v.city}</Detail>
          <Detail label="Address">{v.address_line}</Detail>
          <Detail label="Venue phone">{v.contact_phone}</Detail>
          <Detail label="Time zone">{v.timezone}</Detail>
          <Detail label="Created">{formatDateTime(v.created_at)}</Detail>
          <Detail label="Published">{formatDateTime(v.published_at)}</Detail>
          <Detail label="Rating">{v.rating_avg !== null ? `${v.rating_avg} (${v.rating_count})` : "No ratings yet"}</Detail>
          <div className="sm:col-span-2 lg:col-span-3"><Detail label="Description">{v.description}</Detail></div>
        </DetailGrid>
      </Card>
    </div>
  );
}
