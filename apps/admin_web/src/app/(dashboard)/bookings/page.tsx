import type { Metadata } from "next";
import Link from "next/link";
import { ExportButton } from "@/components/data/export-button";
import { FilterBar } from "@/components/data/filter-bar";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { StatusBadge } from "@/components/data/status-badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Card } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { BOOKING_PAYMENT_STATUSES, BOOKING_REFUND_FILTER, BOOKING_STATUSES, duration, formatDate, formatDateTime, formatMoney } from "@/lib/format";
import { one, PAGE_SIZE, pageOf, type SearchParams } from "@/lib/query";
import type { BookingRow, Paged } from "@/lib/types";

type Opt = { value: string; label: string };
async function options<T extends { id: string }>(path: string, label: (x: T) => string, q: Record<string, string | number> = {}): Promise<Opt[]> {
  const r = await safe(adminGet<T[] | { items: T[] }>(path, q));
  if (!r.ok) return [];
  const items = Array.isArray(r.data) ? r.data : r.data.items;
  return items.map((x) => ({ value: x.id, label: label(x) }));
}

export const metadata: Metadata = { title: "Bookings" };

export default async function BookingsPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const { offset, page } = pageOf(params);
  const filters = {
    q: one(params, "q"), status: one(params, "status"), payment_status: one(params, "payment_status"),
    venue_id: one(params, "venue_id"), customer_id: one(params, "customer_id"), owner_id: one(params, "owner_id"),
    category_id: one(params, "category_id"), city_id: one(params, "city_id"), refund_status: one(params, "refund_status"),
    from: one(params, "from"), to: one(params, "to"),
  };
  const [res, sports, cities, owners, venues] = await Promise.all([
    safe(adminGet<Paged<BookingRow>>("/admin/bookings", { ...filters, limit: PAGE_SIZE, offset })),
    options<{ id: string; name: string }>("/categories", (c) => c.name),
    options<{ id: string; name: string }>("/cities", (c) => c.name),
    options<{ id: string; full_name: string; business_name: string }>("/admin/owners", (o) => `${o.business_name} (${o.full_name})`, { limit: 50, sort: "name", order: "asc" }),
    options<{ id: string; name: string }>("/admin/venues", (v) => v.name, { limit: 50, sort: "name", order: "asc" }),
  ]);
  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        title="Bookings"
        description="Every booking on the platform. Open one to see its full timeline, refunds and disputes, or to cancel it in an exceptional case."
        actions={<ExportButton kind="bookings" query={{ status: filters.status, payment_status: filters.payment_status, venue_id: filters.venue_id, owner_id: filters.owner_id, category_id: filters.category_id, city_id: filters.city_id, refund_status: filters.refund_status, from: filters.from, to: filters.to }} />}
      />
      <Card>
        <FilterBar path="/bookings" params={params} fields={[
          { kind: "search", name: "q", placeholder: "Booking ID, customer or venue" },
          { kind: "select", name: "status", label: "Booking status", options: BOOKING_STATUSES },
          { kind: "select", name: "payment_status", label: "Payment status", options: BOOKING_PAYMENT_STATUSES },
          { kind: "select", name: "refund_status", label: "Refund status", options: BOOKING_REFUND_FILTER },
          { kind: "select", name: "category_id", label: "Sport", options: sports },
          { kind: "select", name: "city_id", label: "City", options: cities },
          { kind: "select", name: "owner_id", label: "Owner", options: owners },
          { kind: "select", name: "venue_id", label: "Venue", options: venues },
          { kind: "date", name: "from", label: "Booking date from" },
          { kind: "date", name: "to", label: "to" },
        ]} />
        {filters.customer_id && (
          <p className="border-b border-border bg-primary-tint/50 px-4 py-2 text-sm">
            Filtered to one customer. <Link href="/bookings" className="text-primary hover:underline">Show everyone</Link>
          </p>
        )}
        {!res.ok ? <div className="p-4"><ErrorState message={`Could not load bookings (${res.error.message}).`} /></div> : res.data.items.length === 0 ? (
          <EmptyState title="No bookings found" description="Try a different search or clear the filters." />
        ) : (
          <>
            <Table>
              <THead><TR><TH>Booking</TH><TH>Customer</TH><TH>Venue / owner</TH><TH>Sport · city</TH><TH>Date &amp; time</TH><TH>Duration</TH><TH className="text-right">Amount</TH><TH>Payment</TH><TH>Status</TH><TH>Refund</TH><TH>Created</TH></TR></THead>
              <TBody>
                {res.data.items.map((b) => (
                  <TR key={b.id}>
                    <TD><Link href={`/bookings/${b.id}`} className="font-medium text-primary hover:underline">{b.booking_code}</Link></TD>
                    <TD><Link href={`/customers/${b.customer_id}`} className="hover:underline">{b.customer_name}</Link></TD>
                    <TD><Link href={`/venues/${b.venue_id}`} className="hover:underline">{b.venue_name}</Link><p className="text-xs text-muted-foreground">{b.owner_name}</p></TD>
                    <TD className="text-xs">{b.sports.join(", ") || "—"}<p className="text-muted-foreground">{b.city ?? "—"}</p></TD>
                    <TD className="whitespace-nowrap">{formatDate(b.booking_date)}<p className="text-xs text-muted-foreground">{b.local_start}–{b.local_end}</p></TD>
                    <TD className="whitespace-nowrap">{duration(b.duration_minutes)}</TD>
                    <TD className="text-right tabular-nums">{formatMoney(b.total_amount_paise, b.currency)}</TD>
                    <TD><StatusBadge status={b.payment_status} /></TD>
                    <TD><StatusBadge status={b.status} /></TD>
                    <TD>{b.refund_status === "none" ? "—" : <StatusBadge status={b.refund_status} />}</TD>
                    <TD className="whitespace-nowrap text-xs text-muted-foreground">{formatDateTime(b.created_at)}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
            <Pagination path="/bookings" params={params} page={page} hasMore={res.data.has_more} shown={res.data.items.length} />
          </>
        )}
      </Card>
    </div>
  );
}
