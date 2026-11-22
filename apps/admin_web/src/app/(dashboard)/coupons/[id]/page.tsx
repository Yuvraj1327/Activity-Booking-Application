import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ActionButton } from "@/components/data/action-button";
import { Detail, DetailGrid } from "@/components/data/detail";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { StatusBadge } from "@/components/data/status-badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDateTime, formatMoney, paiseToRupees } from "@/lib/format";
import { PAGE_SIZE, pageOf, type SearchParams } from "@/lib/query";
import type { Cursor } from "@/lib/types";
import { describe, type Coupon } from "@/lib/coupon";

export const metadata: Metadata = { title: "Coupon" };
type Red = { id: string; booking_id: string; booking_code: string; booking_status: string; payment_status: string; customer_name: string; discount_paise: number; created_at: string };

export default async function CouponPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<SearchParams> }) {
  const { id } = await params;
  const sp = await searchParams;
  const { offset, page } = pageOf(sp);
  const [res, reds] = await Promise.all([safe(adminGet<Coupon>(`/admin/coupons/${encodeURIComponent(id)}`)), safe(adminGet<Cursor<Red> & { items: Red[] }>(`/admin/coupons/${encodeURIComponent(id)}/redemptions`, { limit: PAGE_SIZE, offset }))]);
  if (!res.ok) {
    if (res.error.status === 404 || res.error.status === 422) notFound();
    return <ErrorState message={`Could not load this coupon (${res.error.message}).`} />;
  }
  const c = res.data;
  const back = [`/coupons/${c.id}`, "/coupons"];
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader title={c.code} description={describe(c)} actions={<>
        <StatusBadge status={c.is_active ? "active" : "suspended"} />
        <ActionButton label="Edit limits" title={`Edit ${c.code}`} method="PATCH" path={`/admin/coupons/${c.id}`} refresh={back} description="The code, discount type and value cannot change after creation; create a new coupon instead. Changes apply to future bookings only."
          fields={[{ name: "description", label: "Description", defaultValue: c.description, maxLength: 300 }, { name: "max_discount_paise", label: "Maximum discount (₹)", type: "money", defaultValue: paiseToRupees(c.max_discount_paise) },
            { name: "min_booking_paise", label: "Minimum booking amount (₹)", type: "money", defaultValue: paiseToRupees(c.min_booking_paise) },
            { name: "usage_limit_total", label: "Total redemptions allowed", type: "number", defaultValue: c.usage_limit_total, min: 1 }, { name: "usage_limit_per_user", label: "Per customer", type: "number", defaultValue: c.usage_limit_per_user, min: 1 },
            { name: "first_booking_only", label: "First booking only", type: "checkbox", defaultValue: c.first_booking_only }]} />
      </>} />
      <Card><CardHeader><CardTitle>Rules</CardTitle></CardHeader><DetailGrid>
        <Detail label="Redeemed">{c.redeemed ?? 0}{c.usage_limit_total ? ` of ${c.usage_limit_total}` : " (no limit)"}</Detail><Detail label="Per customer">{c.usage_limit_per_user ?? "No limit"}</Detail>
        <Detail label="Minimum booking">{c.min_booking_paise ? formatMoney(c.min_booking_paise) : "None"}</Detail><Detail label="Valid from">{c.valid_from ? formatDateTime(c.valid_from) : "Any time"}</Detail>
        <Detail label="Valid until">{c.valid_until ? formatDateTime(c.valid_until) : "No end"}</Detail><Detail label="First booking only">{c.first_booking_only ? "Yes" : "No"}</Detail>
        <Detail label="Sports">{c.eligible_category_ids.length ? `${c.eligible_category_ids.length} selected` : "All"}</Detail><Detail label="Cities">{c.eligible_city_ids.length ? `${c.eligible_city_ids.length} selected` : "All"}</Detail><Detail label="Venues">{c.eligible_venue_ids.length ? `${c.eligible_venue_ids.length} selected` : "All"}</Detail>
      </DetailGrid></Card>
      <Card data-testid="redemptions">
        <CardHeader><CardTitle>Redemption history</CardTitle></CardHeader>
        {!reds.ok ? <p className="px-6 pb-6 text-sm text-muted-foreground">Not available ({reds.error.message}).</p> : reds.data.items.length === 0 ? <EmptyState title="Not redeemed yet" /> : (
          <>
            <Table>
              <THead><TR><TH>Booking</TH><TH>Customer</TH><TH className="text-right">Discount</TH><TH>Booking status</TH><TH>Payment</TH><TH>When</TH></TR></THead>
              <TBody>{reds.data.items.map((r) => <TR key={r.id}><TD><Link href={`/bookings/${r.booking_id}`} className="text-primary hover:underline">{r.booking_code}</Link></TD><TD>{r.customer_name}</TD><TD className="text-right tabular-nums">{formatMoney(r.discount_paise)}</TD><TD><StatusBadge status={r.booking_status} /></TD><TD><StatusBadge status={r.payment_status} /></TD><TD className="text-xs">{formatDateTime(r.created_at)}</TD></TR>)}</TBody>
            </Table>
            <Pagination path={`/coupons/${c.id}`} params={sp} page={page} hasMore={reds.data.has_more} shown={reds.data.items.length} />
          </>
        )}
      </Card>
    </div>
  );
}
