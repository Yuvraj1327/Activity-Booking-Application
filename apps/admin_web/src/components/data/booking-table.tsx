import Link from "next/link";
import { StatusBadge } from "@/components/data/status-badge";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { formatDate, formatMoney } from "@/lib/format";
import type { BookingBrief } from "@/lib/types";

export function BriefBookings({ items }: { items: BookingBrief[] }) {
  return (
    <Table>
      <THead><TR><TH>Booking</TH><TH>Venue</TH><TH>Customer</TH><TH>Date</TH><TH>Status</TH><TH>Payment</TH><TH className="text-right">Amount</TH></TR></THead>
      <TBody>
        {items.map((b) => (
          <TR key={b.id}>
            <TD><Link href={`/bookings/${b.id}`} className="font-medium text-primary hover:underline">{b.booking_code}</Link></TD>
            <TD>{b.venue_name}</TD>
            <TD>{b.customer_name}</TD>
            <TD>{formatDate(b.booking_date)}</TD>
            <TD><StatusBadge status={b.status} /></TD>
            <TD><StatusBadge status={b.payment_status} /></TD>
            <TD className="text-right tabular-nums">{formatMoney(b.total_amount_paise, b.currency)}</TD>
          </TR>
        ))}
      </TBody>
    </Table>
  );
}
