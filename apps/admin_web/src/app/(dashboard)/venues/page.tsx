import type { Metadata } from "next";
import Link from "next/link";
import { FilterBar } from "@/components/data/filter-bar";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { StatusBadge } from "@/components/data/status-badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDate } from "@/lib/format";
import { one, PAGE_SIZE, pageOf, type SearchParams } from "@/lib/query";
import type { Paged, VenueRow } from "@/lib/types";
import { BadgeCheck } from "lucide-react";
import { VENUE_STATUSES } from "@/lib/format";
import { href } from "@/lib/query";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Venues" };

export default async function VenuesPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const { offset, page } = pageOf(params);
  const res = await safe(
    adminGet<Paged<VenueRow>>("/admin/venues", {
      q: one(params, "q"), status: one(params, "status"), owner_id: one(params, "owner_id"),
      sort: one(params, "sort"), order: one(params, "order"), limit: PAGE_SIZE, offset,
    }),
  );
  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader title="Venue monitoring" description="Approve, verify and suspend listings. Owners manage the content of their own venues." />
      <div role="tablist" aria-label="Venue queue" className="mb-4 inline-flex rounded-lg border border-border bg-card p-1">
        {[["", "All venues"], ["pending_review", "Pending approval"], ["suspended", "Suspended"]].map(([v, l]) => {
          const on = (one(params, "status") ?? "") === v;
          return <Link key={l} role="tab" aria-selected={on} href={href("/venues", params, { status: v || undefined, page: undefined })} className={cn("rounded-md px-4 py-1.5 text-sm", on ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted")}>{l}</Link>;
        })}
      </div>
      <Card>
        <FilterBar path="/venues" params={params} fields={[
          { kind: "search", name: "q", placeholder: "Search venue, owner or city" },
          { kind: "select", name: "status", label: "Publication", options: VENUE_STATUSES },
          { kind: "select", name: "sort", label: "Sort by", options: [{ value: "created_at", label: "Created" }, { value: "name", label: "Name" }, { value: "bookings", label: "Bookings" }] },
          { kind: "select", name: "order", label: "Order", options: [{ value: "desc", label: "Descending" }, { value: "asc", label: "Ascending" }] },
        ]} />
        {!res.ok ? <div className="p-4"><ErrorState message={`Could not load venues (${res.error.message}).`} /></div> : res.data.items.length === 0 ? (
          <EmptyState title="No venues found" description="Venues appear here when owners create them." />
        ) : (
          <>
            <Table>
              <THead><TR><TH>Venue</TH><TH>Owner</TH><TH>Categories</TH><TH>Location</TH><TH>Status</TH><TH className="text-right">Bookings</TH><TH>{one(params, "status") === "pending_review" ? "Submitted" : "Created"}</TH></TR></THead>
              <TBody>
                {res.data.items.map((v) => (
                  <TR key={v.id}>
                    <TD><Link href={`/venues/${v.id}`} className="font-medium text-primary hover:underline">{v.name}</Link></TD>
                    <TD><Link href={`/owners/${v.owner_id}`} className="hover:underline">{v.owner_name}</Link><p className="text-xs text-muted-foreground">{v.business_name}</p></TD>
                    <TD><div className="flex flex-wrap gap-1">{v.categories.length ? v.categories.map((c) => <Badge key={c} tone="primary">{c}</Badge>) : "—"}</div></TD>
                    <TD>{v.city ?? "—"}</TD>
                    <TD><StatusBadge status={v.status} />{v.is_verified && <BadgeCheck className="ml-1 inline size-4 text-primary" aria-label="Verified" />}{v.open_reports > 0 && <p className="mt-1 text-xs text-destructive">{v.open_reports} open report{v.open_reports > 1 ? "s" : ""}</p>}</TD>
                    <TD className="text-right tabular-nums">{v.confirmed_count}/{v.bookings_count}</TD>
                    <TD className="whitespace-nowrap">{formatDate(one(params, "status") === "pending_review" && v.submitted_at ? v.submitted_at : v.created_at)}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
            <Pagination path="/venues" params={params} page={page} hasMore={res.data.has_more} shown={res.data.items.length} />
          </>
        )}
      </Card>
    </div>
  );
}
