import type { Metadata } from "next";
import Link from "next/link";
import { FilterBar } from "@/components/data/filter-bar";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { StatCard } from "@/components/data/stat-card";
import { StatusBadge } from "@/components/data/status-badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Card } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDateTime, titleCase } from "@/lib/format";
import { one, PAGE_SIZE, pageOf, type SearchParams } from "@/lib/query";
import type { Cursor } from "@/lib/types";

export const metadata: Metadata = { title: "Support tickets" };
type T = { id: string; kind: string; subject: string; status: string; priority: string; user_name: string; user_role: string; booking_code: string | null; assignee_name: string | null; created_at: string };

export default async function SupportPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const { offset, page } = pageOf(params);
  const res = await safe(adminGet<Cursor<T> & { items: T[]; counts: Record<string, number> }>("/admin/support/tickets", {
    status: one(params, "status"), priority: one(params, "priority"), kind: one(params, "kind"), q: one(params, "q"), limit: PAGE_SIZE, offset,
  }));
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader title="Support tickets" description="Support requests, feedback and issue reports sent from the apps. Urgent first." />
      {res.ok && (
        <div className="grid gap-4 sm:grid-cols-4">
          {(["open", "in_progress", "resolved", "closed"] as const).map((s) => <StatCard key={s} label={titleCase(s)} value={String(res.data.counts[s] ?? 0)} tone={s === "open" ? "warning" : "primary"} />)}
        </div>
      )}
      <Card>
        <FilterBar path="/support" params={params} fields={[
          { kind: "search", name: "q", placeholder: "Subject, customer name or e-mail" },
          { kind: "select", name: "status", label: "Status", options: [{ value: "active", label: "Needs attention" }, ...["open", "in_progress", "resolved", "closed"].map((v) => ({ value: v, label: titleCase(v) }))] },
          { kind: "select", name: "priority", label: "Priority", options: ["urgent", "high", "normal", "low"] },
          { kind: "select", name: "kind", label: "Type", options: ["support", "feedback", "issue"] },
        ]} />
        {!res.ok ? <div className="p-4"><ErrorState message={`Could not load tickets (${res.error.message}).`} /></div> : res.data.items.length === 0 ? <EmptyState title="No tickets" description="Messages from Help & Support in the apps appear here." /> : (
          <>
            <Table>
              <THead><TR><TH>Subject</TH><TH>From</TH><TH>Type</TH><TH>Priority</TH><TH>Status</TH><TH>Booking</TH><TH>Assigned</TH><TH>Received</TH></TR></THead>
              <TBody>{res.data.items.map((t) => (
                <TR key={t.id}>
                  <TD><Link href={`/support/${t.id}`} className="font-medium text-primary hover:underline">{t.subject}</Link></TD>
                  <TD>{t.user_name}<p className="text-xs text-muted-foreground">{titleCase(t.user_role)}</p></TD><TD>{titleCase(t.kind)}</TD>
                  <TD><StatusBadge status={t.priority} /></TD><TD><StatusBadge status={t.status} /></TD><TD>{t.booking_code ?? "—"}</TD><TD>{t.assignee_name ?? "—"}</TD><TD className="whitespace-nowrap text-xs">{formatDateTime(t.created_at)}</TD>
                </TR>
              ))}</TBody>
            </Table>
            <Pagination path="/support" params={params} page={page} hasMore={res.data.has_more} shown={res.data.items.length} />
          </>
        )}
      </Card>
    </div>
  );
}
