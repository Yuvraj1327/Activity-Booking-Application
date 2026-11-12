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
import type { CustomerRow, Paged } from "@/lib/types";

export const metadata: Metadata = { title: "Customers" };

export default async function CustomersPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const { offset, page } = pageOf(params);
  const res = await safe(
    adminGet<Paged<CustomerRow>>("/admin/customers", {
      q: one(params, "q"), status: one(params, "status"), sort: one(params, "sort"), order: one(params, "order"),
      limit: PAGE_SIZE, offset,
    }),
  );
  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader title="Customers" description="Registered customers. Phone numbers are masked in lists." actions={<ExportButton kind="customers" label="Customer report (CSV)" />} />
      <Card>
        <FilterBar path="/customers" params={params} fields={[
          { kind: "search", name: "q", placeholder: "Search name or e-mail" },
          { kind: "select", name: "status", label: "Account status", options: ["active", "suspended"] },
          { kind: "select", name: "sort", label: "Sort by", options: [{ value: "created_at", label: "Registered" }, { value: "name", label: "Name" }, { value: "bookings", label: "Bookings" }] },
          { kind: "select", name: "order", label: "Order", options: [{ value: "desc", label: "Descending" }, { value: "asc", label: "Ascending" }] },
        ]} />
        {!res.ok ? <div className="p-4"><ErrorState message={`Could not load customers (${res.error.message}).`} /></div> : res.data.items.length === 0 ? (
          <EmptyState title="No customers found" description="Try a different search or clear the filters." />
        ) : (
          <>
            <Table>
              <THead><TR><TH>Customer</TH><TH>Contact</TH><TH>Status</TH><TH className="text-right">Bookings</TH><TH>Registered</TH></TR></THead>
              <TBody>
                {res.data.items.map((c) => (
                  <TR key={c.id}>
                    <TD><Link href={`/customers/${c.id}`} className="font-medium text-primary hover:underline">{c.full_name}</Link></TD>
                    <TD><p>{c.email ?? "—"}</p><p className="text-xs text-muted-foreground">{c.phone_masked ?? ""}</p></TD>
                    <TD><StatusBadge status={c.status} /></TD>
                    <TD className="text-right tabular-nums">{c.confirmed_count}/{c.bookings_count}</TD>
                    <TD className="whitespace-nowrap">{formatDate(c.created_at)}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
            <Pagination path="/customers" params={params} page={page} hasMore={res.data.has_more} shown={res.data.items.length} />
          </>
        )}
      </Card>
    </div>
  );
}
