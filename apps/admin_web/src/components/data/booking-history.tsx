import Link from "next/link";
import { Pagination } from "@/components/data/pagination";
import { StatusBadge } from "@/components/data/status-badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDate, formatDateTime, formatMoney } from "@/lib/format";
import { pageOf, PAGE_SIZE, type SearchParams } from "@/lib/query";
import type { BookingRow, Paged } from "@/lib/types";

/** Complete, paginated booking history of one customer / owner / venue (its own page parameter, so it can sit next to other lists). */
export async function BookingHistory({ filter, id, path, params, title = "Booking history" }: {
  filter: "customer_id" | "owner_id" | "venue_id"; id: string; path: string; params: SearchParams; title?: string;
}) {
  const { offset, page } = pageOf(params, "bpage");
  const res = await safe(adminGet<Paged<BookingRow>>("/admin/bookings", { [filter]: id, limit: PAGE_SIZE, offset }));
  return (
    <Card id="bookings">
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>{title}</CardTitle>
        <Link href={`/bookings?${filter}=${id}`} className="text-sm text-primary hover:underline">Open in Bookings</Link>
      </CardHeader>
      {!res.ok ? <div className="p-4"><ErrorState message={`Could not load bookings (${res.error.message}).`} /></div> : res.data.items.length === 0 ? <EmptyState title="No bookings yet" /> : (
        <>
          <Table>
            <THead><TR><TH>Booking</TH>{filter !== "customer_id" && <TH>Customer</TH>}{filter !== "venue_id" && <TH>Venue</TH>}<TH>Date</TH><TH className="text-right">Amount</TH><TH>Payment</TH><TH>Status</TH><TH>Refund</TH><TH>Created</TH></TR></THead>
            <TBody>{res.data.items.map((b) => (
              <TR key={b.id}>
                <TD><Link href={`/bookings/${b.id}`} className="font-medium text-primary hover:underline">{b.booking_code}</Link></TD>
                {filter !== "customer_id" && <TD>{b.customer_name}</TD>}
                {filter !== "venue_id" && <TD>{b.venue_name}</TD>}
                <TD className="whitespace-nowrap">{formatDate(b.booking_date)} <span className="text-xs text-muted-foreground">{b.local_start}</span></TD>
                <TD className="text-right tabular-nums">{formatMoney(b.total_amount_paise, b.currency)}</TD>
                <TD><StatusBadge status={b.payment_status} /></TD><TD><StatusBadge status={b.status} /></TD>
                <TD>{b.refund_status === "none" ? "—" : <StatusBadge status={b.refund_status} />}</TD>
                <TD className="whitespace-nowrap text-xs text-muted-foreground">{formatDateTime(b.created_at)}</TD>
              </TR>
            ))}</TBody>
          </Table>
          <Pagination path={path} params={params} page={page} hasMore={res.data.has_more} shown={res.data.items.length} pageParam="bpage" anchor="bookings" />
        </>
      )}
    </Card>
  );
}
