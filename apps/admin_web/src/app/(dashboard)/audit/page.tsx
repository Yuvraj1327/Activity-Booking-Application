import type { Metadata } from "next";
import { FilterBar } from "@/components/data/filter-bar";
import { Mono } from "@/components/data/detail";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Card } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDateTime } from "@/lib/format";
import { one, PAGE_SIZE, pageOf, type SearchParams } from "@/lib/query";
import type { AuditRow, Paged } from "@/lib/types";

export const metadata: Metadata = { title: "Audit log" };

const ACTIONS = ["admin.account_status_changed", "admin.export", "profile.registered", "venue.created", "venue.published"];

export default async function AuditPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const { offset, page } = pageOf(params);
  const res = await safe(adminGet<Paged<AuditRow>>("/admin/audit-logs", { action: one(params, "action"), limit: PAGE_SIZE, offset }));
  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader title="Audit log" description="Sensitive actions, newest first. The log is append-only." />
      <Card>
        <FilterBar path="/audit" params={params} fields={[{ kind: "select", name: "action", label: "Action", options: ACTIONS }]} />
        {!res.ok ? <div className="p-4"><ErrorState message={`Could not load the audit log (${res.error.message}).`} /></div> : res.data.items.length === 0 ? (
          <EmptyState title="No audit entries" />
        ) : (
          <>
            <Table>
              <THead><TR><TH>When</TH><TH>Action</TH><TH>Actor</TH><TH>Target</TH><TH>Details</TH></TR></THead>
              <TBody>{res.data.items.map((a) => (
                <TR key={a.id}>
                  <TD className="whitespace-nowrap text-xs">{formatDateTime(a.created_at)}</TD>
                  <TD className="font-medium">{a.action}</TD>
                  <TD>{a.actor_role ?? "system"}</TD>
                  <TD><span className="text-xs text-muted-foreground">{a.entity_type}</span> <Mono>{a.entity_id?.slice(0, 8) ?? ""}</Mono></TD>
                  <TD className="max-w-xs truncate text-xs text-muted-foreground" title={JSON.stringify(a.metadata)}>{Object.entries(a.metadata).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`).join(" · ")}</TD>
                </TR>
              ))}</TBody>
            </Table>
            <Pagination path="/audit" params={params} page={page} hasMore={res.data.has_more} shown={res.data.items.length} />
          </>
        )}
      </Card>
    </div>
  );
}
