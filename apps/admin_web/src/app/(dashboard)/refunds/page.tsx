import type { Metadata } from "next";
import Link from "next/link";
import { ExportButton } from "@/components/data/export-button";
import { FilterBar } from "@/components/data/filter-bar";
import { Mono } from "@/components/data/detail";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { StatusBadge } from "@/components/data/status-badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Card } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDateTime, formatMoney, REFUND_STATUSES } from "@/lib/format";
import { one, PAGE_SIZE, pageOf, type SearchParams } from "@/lib/query";
import type { Cursor } from "@/lib/types";

export const metadata: Metadata = { title: "Refunds" };

type R = { id: string; payment_id: string; booking_id: string; booking_code: string; venue_name: string; amount_paise: number; status: string; source: string; reason: string | null; failure_reason: string | null; created_at: string; processed_at: string | null };

export default async function RefundsPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const { offset, page } = pageOf(params);
  const f = { status: one(params, "status"), q: one(params, "q"), from: one(params, "from"), to: one(params, "to") };
  const res = await safe(adminGet<Cursor<R> & { items: R[] }>("/admin/refunds", { ...f, limit: PAGE_SIZE, offset }));
  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader title="Refunds" description="Every refund, whether started here or in the Razorpay dashboard. Refunds start from a payment." actions={<ExportButton kind="refunds" query={{ status: f.status, from: f.from, to: f.to }} />} />
      <Card>
        <FilterBar path="/refunds" params={params} fields={[
          { kind: "search", name: "q", placeholder: "Booking code or Razorpay refund id" },
          { kind: "select", name: "status", label: "Status", options: REFUND_STATUSES },
          { kind: "date", name: "from", label: "From" }, { kind: "date", name: "to", label: "to" },
        ]} />
        {!res.ok ? <div className="p-4"><ErrorState message={`Could not load refunds (${res.error.message}).`} /></div> : res.data.items.length === 0 ? (
          <EmptyState title="No refunds" description="Refunds appear here when they are started or reported by Razorpay." />
        ) : (
          <>
            <Table>
              <THead><TR><TH>Refund</TH><TH>Booking</TH><TH>Venue</TH><TH className="text-right">Amount</TH><TH>Status</TH><TH>Source</TH><TH>Reason / failure</TH><TH>Created</TH></TR></THead>
              <TBody>{res.data.items.map((r) => (
                <TR key={r.id}>
                  <TD><Link href={`/refunds/${r.id}`} className="font-medium text-primary hover:underline"><Mono>{r.id.slice(0, 8)}</Mono></Link></TD>
                  <TD><Link href={`/bookings/${r.booking_id}`} className="hover:underline">{r.booking_code}</Link></TD><TD>{r.venue_name}</TD>
                  <TD className="text-right tabular-nums">{formatMoney(r.amount_paise)}</TD><TD><StatusBadge status={r.status} /></TD><TD>{r.source === "gateway" ? "Razorpay" : "Admin"}</TD>
                  <TD className="max-w-xs truncate">{r.failure_reason ?? r.reason ?? "—"}</TD><TD className="whitespace-nowrap text-xs">{formatDateTime(r.created_at)}</TD>
                </TR>
              ))}</TBody>
            </Table>
            <Pagination path="/refunds" params={params} page={page} hasMore={res.data.has_more} shown={res.data.items.length} />
          </>
        )}
      </Card>
    </div>
  );
}
