import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { BriefBookings } from "@/components/data/booking-table";
import { Detail, DetailGrid } from "@/components/data/detail";
import { PageHeader } from "@/components/data/page-header";
import { StatCard } from "@/components/data/stat-card";
import { StatusBadge } from "@/components/data/status-badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { StatusControl } from "@/components/data/status-control";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDateTime, formatMoney } from "@/lib/format";
import type { CustomerDetail } from "@/lib/types";

export const metadata: Metadata = { title: "Customer" };

export default async function CustomerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const res = await safe(adminGet<CustomerDetail>(`/admin/customers/${encodeURIComponent(id)}`));
  if (!res.ok) {
    if (res.error.status === 404 || res.error.status === 422) notFound();
    return <ErrorState message={`Could not load this customer (${res.error.message}).`} />;
  }
  const c = res.data;
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader title={c.full_name} description="Customer" actions={<><StatusBadge status={c.status} /><StatusControl role="customer" id={c.id} name={c.full_name} status={c.status} /></>} />
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Bookings" value={String(c.bookings_count)} hint={`${c.confirmed_count} confirmed · ${c.cancelled_count} cancelled`} />
        <StatCard label="Gross paid" value={formatMoney(c.gross_paid_paise)} hint="Captured payments" />
        <StatCard label="Account status" value={c.status === "active" ? "Active" : "Suspended"} tone={c.status === "active" ? "success" : "danger"} />
      </div>
      <Card>
        <CardHeader><CardTitle>Profile</CardTitle></CardHeader>
        <DetailGrid>
          <Detail label="E-mail">{c.email}</Detail>
          <Detail label="Phone">{c.phone}</Detail>
          <Detail label="Registered">{formatDateTime(c.created_at)}</Detail>
        </DetailGrid>
      </Card>
      <Card>
        <CardHeader><CardTitle>Booking history</CardTitle></CardHeader>
        {c.bookings.length === 0 ? <EmptyState title="No bookings yet" /> : <BriefBookings items={c.bookings} />}
      </Card>
    </div>
  );
}
