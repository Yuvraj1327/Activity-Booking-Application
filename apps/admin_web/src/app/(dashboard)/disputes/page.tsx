import type { Metadata } from "next";
import Link from "next/link";
import { FilterBar } from "@/components/data/filter-bar";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { StatusBadge } from "@/components/data/status-badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Card } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDateTime, titleCase } from "@/lib/format";
import { one, PAGE_SIZE, pageOf, type SearchParams } from "@/lib/query";
import type { Cursor } from "@/lib/types";

export const metadata: Metadata = { title: "Disputes" };
type D = { id: string; booking_id: string; booking_code: string; venue_name: string; customer_name: string; subject: string; status: string; priority: string; raised_by_role: string; created_at: string };

export default async function DisputesPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const { offset, page } = pageOf(params);
  const res = await safe(adminGet<Cursor<D> & { items: D[] }>("/admin/disputes", { status: one(params, "status"), priority: one(params, "priority"), limit: PAGE_SIZE, offset }));
  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader title="Booking disputes" description="Open a dispute from a booking. Notes, evidence, refunds and cancellations are all kept on one timeline." />
      <Card>
        <FilterBar path="/disputes" params={params} fields={[
          { kind: "select", name: "status", label: "Status", options: ["open", "investigating", "resolved", "rejected"] },
          { kind: "select", name: "priority", label: "Priority", options: ["urgent", "high", "normal", "low"] },
        ]} />
        {!res.ok ? <div className="p-4"><ErrorState message={`Could not load disputes (${res.error.message}).`} /></div> : res.data.items.length === 0 ? <EmptyState title="No disputes" description="Open one from a booking's page." /> : (
          <>
            <Table>
              <THead><TR><TH>Dispute</TH><TH>Booking</TH><TH>Customer</TH><TH>Raised by</TH><TH>Priority</TH><TH>Status</TH><TH>Opened</TH></TR></THead>
              <TBody>{res.data.items.map((d) => (
                <TR key={d.id}>
                  <TD><Link href={`/disputes/${d.id}`} className="font-medium text-primary hover:underline">{d.subject}</Link></TD>
                  <TD><Link href={`/bookings/${d.booking_id}`} className="hover:underline">{d.booking_code}</Link><p className="text-xs text-muted-foreground">{d.venue_name}</p></TD>
                  <TD>{d.customer_name}</TD><TD>{titleCase(d.raised_by_role)}</TD><TD><StatusBadge status={d.priority} /></TD><TD><StatusBadge status={d.status} /></TD><TD className="whitespace-nowrap text-xs">{formatDateTime(d.created_at)}</TD>
                </TR>
              ))}</TBody>
            </Table>
            <Pagination path="/disputes" params={params} page={page} hasMore={res.data.has_more} shown={res.data.items.length} />
          </>
        )}
      </Card>
    </div>
  );
}
