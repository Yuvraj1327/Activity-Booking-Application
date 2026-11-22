import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { AccountHistory } from "@/components/data/account-history";
import { BookingHistory } from "@/components/data/booking-history";
import { Detail, DetailGrid } from "@/components/data/detail";
import { PageHeader } from "@/components/data/page-header";
import { StatCard } from "@/components/data/stat-card";
import { StatusBadge } from "@/components/data/status-badge";
import { ErrorState } from "@/components/data/states";
import { StatusControl } from "@/components/data/status-control";
import { Alert } from "@/components/ui/alert";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { adminGet, safe } from "@/lib/admin-api";
import { hasPermission } from "@/lib/admin-access";
import { formatDateTime, formatMoney } from "@/lib/format";
import type { SearchParams } from "@/lib/query";
import type { CustomerDetail } from "@/lib/types";

export const metadata: Metadata = { title: "Customer" };

export default async function CustomerPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<SearchParams> }) {
  const { id } = await params;
  const sp = await searchParams;
  const [res, canManage] = await Promise.all([safe(adminGet<CustomerDetail>(`/admin/customers/${encodeURIComponent(id)}`)), hasPermission("customers.manage")]);
  if (!res.ok) {
    if (res.error.status === 404 || res.error.status === 422) notFound();
    return <ErrorState message={`Could not load this customer (${res.error.message}).`} />;
  }
  const c = res.data;
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader title={c.full_name} description={c.email ?? undefined} actions={<><StatusBadge status={c.status} />{canManage && <StatusControl role="customer" id={c.id} name={c.full_name} status={c.status} />}</>} />
      {c.has_open_dispute && <Alert data-testid="open-dispute-note">This customer has a booking dispute in progress. <Link className="text-primary underline" href="/disputes?status=open">View disputes</Link></Alert>}
      {c.deletion_requested_at && <Alert>The customer asked for account deletion on {formatDateTime(c.deletion_requested_at)}. Process it according to your data-retention policy.</Alert>}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Bookings" value={String(c.bookings_count)} />
        <StatCard label="Confirmed" value={String(c.confirmed_count)} tone="success" />
        <StatCard label="Completed" value={String(c.completed_count)} tone="success" />
        <StatCard label="Cancelled" value={String(c.cancelled_count)} tone="danger" />
        <StatCard label="Paid" value={formatMoney(c.gross_paid_paise)} hint={`${formatMoney(c.refunded_paise)} refunded`} />
      </div>
      <Card>
        <CardHeader><CardTitle>Profile</CardTitle></CardHeader>
        <DetailGrid>
          <Detail label="E-mail">{c.email}</Detail>
          <Detail label="Phone">{c.phone}</Detail>
          <Detail label="Account status"><StatusBadge status={c.status} /></Detail>
          <Detail label="Registered">{formatDateTime(c.created_at)}</Detail>
          <Detail label="App language">{c.language}</Detail>
        </DetailGrid>
      </Card>
      <BookingHistory filter="customer_id" id={c.id} path={`/customers/${c.id}`} params={sp} title="Booking history" />
      <AccountHistory kind="customers" id={c.id} />
    </div>
  );
}
