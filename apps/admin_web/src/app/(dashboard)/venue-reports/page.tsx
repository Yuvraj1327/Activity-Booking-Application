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

export const metadata: Metadata = { title: "Venue reports" };

type R = { id: string; venue_id: string; venue_name: string; reporter_name: string | null; reason: string; details: string | null; status: string; created_at: string };

export default async function ReportsPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const { offset, page } = pageOf(params);
  const res = await safe(adminGet<Cursor<R> & { items: R[] }>("/admin/venue-reports", { status: one(params, "status"), venue_id: one(params, "venue_id"), limit: PAGE_SIZE, offset }));
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title="Reported venues" description="Listings flagged by customers. Open a report to review it, then close it with a note." />
      <Card>
        <FilterBar path="/venue-reports" params={params} fields={[{ kind: "select", name: "status", label: "Status", options: ["open", "reviewing", "dismissed", "action_taken"] }]} />
        {!res.ok ? <div className="p-4"><ErrorState message={`Could not load reports (${res.error.message}).`} /></div> : res.data.items.length === 0 ? <EmptyState title="No reports" description="Customers can report a venue from the app." /> : (
          <>
            <Table>
              <THead><TR><TH>Venue</TH><TH>Reason</TH><TH>Reported by</TH><TH>Status</TH><TH>When</TH></TR></THead>
              <TBody>{res.data.items.map((r) => (
                <TR key={r.id}>
                  <TD><Link href={`/venue-reports/${r.id}`} className="font-medium text-primary hover:underline">{r.venue_name}</Link></TD>
                  <TD>{titleCase(r.reason)}{r.details && <p className="max-w-xs truncate text-xs text-muted-foreground">{r.details}</p>}</TD>
                  <TD>{r.reporter_name ?? "—"}</TD><TD><StatusBadge status={r.status} /></TD><TD className="whitespace-nowrap text-xs">{formatDateTime(r.created_at)}</TD>
                </TR>
              ))}</TBody>
            </Table>
            <Pagination path="/venue-reports" params={params} page={page} hasMore={res.data.has_more} shown={res.data.items.length} />
          </>
        )}
      </Card>
    </div>
  );
}
