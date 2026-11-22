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

const ENTITIES = ["profile", "owner", "venue", "booking", "payment", "refund", "dispute", "payout", "finance_config", "coupon", "category", "cms_content", "support_ticket", "admin_role", "platform_setting", "owner_kyc_document", "venue_report", "reconciliation_run"];

const show = (v: unknown): string => (v === null || v === undefined ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v));

function Change({ meta }: { meta: Record<string, unknown> }) {
  const before = meta.before as Record<string, unknown> | undefined;
  const after = meta.after as Record<string, unknown> | undefined;
  const rest = Object.entries(meta).filter(([k]) => !["before", "after", "reason", "from", "to"].includes(k));
  const keys = Array.from(new Set([...Object.keys(before ?? {}), ...Object.keys(after ?? {})]));
  return (
    <div className="space-y-1 text-xs">
      {keys.length > 0 && (
        <ul data-testid="audit-diff">{keys.map((k) => (
          <li key={k}><span className="font-medium">{k}:</span> <span className="text-muted-foreground line-through decoration-muted-foreground/40">{show(before?.[k])}</span> → <span>{show(after?.[k])}</span></li>
        ))}</ul>
      )}
      {typeof meta.reason === "string" && <p>Reason: “{meta.reason}”</p>}
      {rest.length > 0 && <p className="text-muted-foreground">{rest.map(([k, v]) => `${k}: ${show(v)}`).join(" · ")}</p>}
    </div>
  );
}

export default async function AuditPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const { offset, page } = pageOf(params);
  const [res, actions] = await Promise.all([
    safe(adminGet<Paged<AuditRow>>("/admin/audit-logs", {
      action: one(params, "action"), entity_type: one(params, "entity_type"), entity_id: one(params, "entity_id"), actor_id: one(params, "actor_id"),
      from: one(params, "from"), to: one(params, "to"), limit: PAGE_SIZE, offset,
    })),
    safe(adminGet<{ items: string[] }>("/admin/audit-actions")),
  ]);
  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader title="Audit log" description="Who did what, to which record, with the value before and after and the reason. Newest first. The log is append-only." />
      <Card>
        <FilterBar path="/audit" params={params} fields={[
          { kind: "select", name: "action", label: "Action", options: actions.ok ? actions.data.items : [] },
          { kind: "select", name: "entity_type", label: "Record type", options: ENTITIES },
          { kind: "search", name: "entity_id", placeholder: "Record ID" },
          { kind: "search", name: "actor_id", placeholder: "Administrator ID" },
          { kind: "date", name: "from", label: "From" }, { kind: "date", name: "to", label: "To" },
        ]} />
        {!res.ok ? <div className="p-4"><ErrorState message={`Could not load the audit log (${res.error.message}).`} /></div> : res.data.items.length === 0 ? (
          <EmptyState title="No audit entries" />
        ) : (
          <>
            <Table>
              <THead><TR><TH>When</TH><TH>Action</TH><TH>Who</TH><TH>Record</TH><TH>Change</TH></TR></THead>
              <TBody>{res.data.items.map((a) => (
                <TR key={a.id}>
                  <TD className="whitespace-nowrap text-xs">{formatDateTime(a.created_at)}{a.request_id && <p className="font-mono text-[10px] text-muted-foreground" title="Request ID">{a.request_id.slice(0, 8)}</p>}</TD>
                  <TD className="font-medium">{a.action}</TD>
                  <TD>{a.actor_name ?? a.actor_role ?? "system"}<p className="text-xs text-muted-foreground">{a.actor_role}</p></TD>
                  <TD><span className="text-xs text-muted-foreground">{a.entity_type}</span> <Mono>{a.entity_id?.slice(0, 8) ?? ""}</Mono></TD>
                  <TD className="max-w-md"><Change meta={a.metadata} /></TD>
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
