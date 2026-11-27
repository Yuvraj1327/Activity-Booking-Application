import type { Metadata } from "next";
import { CommissionTabs } from "@/components/data/commission-tabs";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { SCOPE_LABEL, type HistoryRow } from "@/lib/commission";
import { formatDateTime } from "@/lib/format";
import { one, PAGE_SIZE, pageOf, resolveRange, type SearchParams } from "@/lib/query";
import type { Cursor } from "@/lib/types";

export const metadata: Metadata = { title: "Commission history" };
type Cat = { id: string; name: string };

export default async function HistoryPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const { offset, page } = pageOf(params);
  const hasRange = Boolean(one(params, "from") || one(params, "to") || one(params, "preset"));
  const range = resolveRange(params);
  const q = { scope: one(params, "scope"), venue_id: one(params, "venue_id"), category_id: one(params, "category_id"), from: hasRange ? range.from : undefined, to: hasRange ? range.to : undefined };
  const [res, cats] = await Promise.all([safe(adminGet<Cursor<HistoryRow>>("/admin/commission/history", { ...q, limit: PAGE_SIZE, offset })), safe(adminGet<{ items: Cat[] }>("/admin/categories"))]);
  const sel = "h-9 rounded-md border border-border bg-background px-2 text-sm";
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader title="Commission history" description="Every change ever made, kept permanently. Rows cannot be edited or deleted. Each version stays in force until the next one starts." />
      <CommissionTabs current="/commission/history" />
      <Card>
        <form method="get" action="/commission/history" className="flex flex-wrap items-end gap-3 border-b border-border p-4" role="search">
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">Scope
            <select name="scope" defaultValue={q.scope ?? ""} className={sel}><option value="">All</option><option value="global">Global</option><option value="activity">Activity</option><option value="venue">Venue</option></select></label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">Activity
            <select name="category_id" defaultValue={q.category_id ?? ""} className={sel}><option value="">All</option>{cats.ok && cats.data.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">Venue ID
            <input name="venue_id" defaultValue={q.venue_id ?? ""} placeholder="Venue UUID" className={`${sel} w-72`} /></label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">Changed from<input type="date" name="from" defaultValue={hasRange ? range.from : ""} className={sel} /></label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">to<input type="date" name="to" defaultValue={hasRange ? range.to : ""} className={sel} /></label>
          <button type="submit" className="h-9 rounded-md bg-primary px-3 text-sm text-primary-foreground">Filter</button>
          <a href="/commission/history" className="h-9 self-end py-2 text-sm text-muted-foreground hover:underline">Clear</a>
        </form>
        {!res.ok ? <div className="p-4"><ErrorState message={`Could not load history (${res.error.message}).`} /></div> : res.data.items.length === 0 ? <EmptyState title="No history matches" /> : (
          <>
            <Table>
              <THead><TR><TH>Changed</TH><TH>Scope</TH><TH>Applies to</TH><TH>Previous</TH><TH>New</TH><TH>State</TH><TH>In force</TH><TH>By</TH><TH>Reason</TH></TR></THead>
              <TBody>{res.data.items.map((h) => (
                <TR key={h.id}>
                  <TD className="whitespace-nowrap text-xs">{formatDateTime(h.created_at)}<p className="text-muted-foreground">v{h.version}</p></TD>
                  <TD>{SCOPE_LABEL[h.scope] ?? h.scope}</TD>
                  <TD>{h.scope === "global" ? "All bookings" : (h.venue_name ?? h.category_name)}</TD>
                  <TD className="tabular-nums">{h.previous_pct ?? "—"}</TD><TD className="font-medium tabular-nums">{h.commission_pct}</TD>
                  <TD><Badge>{h.is_active ? "Active" : "Inactive"}</Badge></TD>
                  <TD className="whitespace-nowrap text-xs">{formatDateTime(h.effective_from)} →<br />{h.effective_to ? formatDateTime(h.effective_to) : "until changed"}</TD>
                  <TD>{h.changed_by_name ?? "—"}</TD><TD className="max-w-xs text-xs">{h.reason}</TD>
                </TR>
              ))}</TBody>
            </Table>
            <Pagination path="/commission/history" params={params} page={page} hasMore={res.data.has_more} shown={res.data.items.length} />
          </>
        )}
      </Card>
    </div>
  );
}
