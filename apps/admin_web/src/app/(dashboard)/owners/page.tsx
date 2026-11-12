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
import { formatDate } from "@/lib/format";
import { one, PAGE_SIZE, pageOf, type SearchParams } from "@/lib/query";
import type { OwnerRow, Paged } from "@/lib/types";

export const metadata: Metadata = { title: "Owners" };

export default async function OwnersPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const { offset, page } = pageOf(params);
  const res = await safe(
    adminGet<Paged<OwnerRow>>("/admin/owners", {
      q: one(params, "q"), status: one(params, "status"), sort: one(params, "sort"), order: one(params, "order"),
      limit: PAGE_SIZE, offset,
    }),
  );
  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader title="Venue owners" description="Monitor registered owners. Admins do not create or manage their listings." actions={<ExportButton kind="owners" label="Owner report (CSV)" />} />
      <Card>
        <FilterBar path="/owners" params={params} fields={[
          { kind: "search", name: "q", placeholder: "Search name, e-mail or business" },
          { kind: "select", name: "status", label: "Account status", options: ["active", "suspended"] },
          { kind: "select", name: "sort", label: "Sort by", options: [{ value: "created_at", label: "Registered" }, { value: "name", label: "Name" }, { value: "venues", label: "Venues" }, { value: "bookings", label: "Bookings" }] },
          { kind: "select", name: "order", label: "Order", options: [{ value: "desc", label: "Descending" }, { value: "asc", label: "Ascending" }] },
        ]} />
        {!res.ok ? <div className="p-4"><ErrorState message={`Could not load owners (${res.error.message}).`} /></div> : res.data.items.length === 0 ? (
          <EmptyState title="No owners found" description="Try a different search or clear the filters." />
        ) : (
          <>
            <Table>
              <THead><TR><TH>Owner</TH><TH>Business</TH><TH>Contact</TH><TH>Status</TH><TH className="text-right">Venues</TH><TH className="text-right">Bookings</TH><TH>Registered</TH></TR></THead>
              <TBody>
                {res.data.items.map((o) => (
                  <TR key={o.id}>
                    <TD><Link href={`/owners/${o.id}`} className="font-medium text-primary hover:underline">{o.full_name}</Link></TD>
                    <TD>{o.business_name}</TD>
                    <TD><p>{o.email ?? "—"}</p><p className="text-xs text-muted-foreground">{o.phone_masked ?? ""}</p></TD>
                    <TD><StatusBadge status={o.status} /></TD>
                    <TD className="text-right tabular-nums">{o.published_venues_count}/{o.venues_count}</TD>
                    <TD className="text-right tabular-nums">{o.bookings_count}</TD>
                    <TD className="whitespace-nowrap">{formatDate(o.created_at)}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
            <Pagination path="/owners" params={params} page={page} hasMore={res.data.has_more} shown={res.data.items.length} />
          </>
        )}
      </Card>
    </div>
  );
}
