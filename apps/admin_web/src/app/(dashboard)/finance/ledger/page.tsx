import type { Metadata } from "next";
import Link from "next/link";
import { DateRangeFilter } from "@/components/data/date-range-filter";
import { ExportButton } from "@/components/data/export-button";
import { FinanceTabs } from "@/components/data/finance-tabs";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { StatusBadge } from "@/components/data/status-badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Card } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDateTime, formatMoney } from "@/lib/format";
import { one, PAGE_SIZE, pageOf, resolveRange, type SearchParams } from "@/lib/query";
import type { Cursor } from "@/lib/types";

export const metadata: Metadata = { title: "Ledger" };
type E = { id: string; kind: string; booking_id: string; booking_code: string; venue_name: string; owner_name: string; config_version: number; gross_paise: number; tax_paise: number; owner_amount_paise: number; platform_amount_paise: number; fee_paise: number; commission_paise: number; occurred_at: string };

export default async function LedgerPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const range = resolveRange(params);
  const { offset, page } = pageOf(params);
  const res = await safe(adminGet<Cursor<E> & { items: E[] }>("/admin/finance/ledger", { from: range.from, to: range.to, owner_id: one(params, "owner_id"), limit: PAGE_SIZE, offset }));
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader title="Ledger" description="One immutable row per captured payment and per processed refund. Gross = owner share + platform share + tax."
        actions={<ExportButton kind="ledger" query={{ from: range.from, to: range.to, owner_id: one(params, "owner_id") }} />} />
      <FinanceTabs current="/finance/ledger" />
      <DateRangeFilter path="/finance/ledger" params={params} range={range} />
      <Card>
        {!res.ok ? <div className="p-4"><ErrorState message={`Could not load the ledger (${res.error.message}).`} /></div> : res.data.items.length === 0 ? <EmptyState title="No ledger entries in this period" description="Entries exist only for payments captured under an approved configuration." /> : (
          <>
            <Table>
              <THead><TR><TH>When</TH><TH>Entry</TH><TH>Booking</TH><TH>Owner</TH><TH className="text-right">Gross</TH><TH className="text-right">Owner share</TH><TH className="text-right">Platform</TH><TH className="text-right">Tax</TH><TH>Rule</TH></TR></THead>
              <TBody>{res.data.items.map((e) => (
                <TR key={e.id}>
                  <TD className="whitespace-nowrap text-xs">{formatDateTime(e.occurred_at)}</TD><TD><StatusBadge status={e.kind === "sale" ? "paid" : "refunded"} /></TD>
                  <TD><Link href={`/bookings/${e.booking_id}`} className="text-primary hover:underline">{e.booking_code}</Link><p className="text-xs text-muted-foreground">{e.venue_name}</p></TD><TD>{e.owner_name}</TD>
                  <TD className="text-right tabular-nums">{formatMoney(e.gross_paise)}</TD><TD className="text-right tabular-nums">{formatMoney(e.owner_amount_paise)}</TD><TD className="text-right tabular-nums">{formatMoney(e.platform_amount_paise)}</TD><TD className="text-right tabular-nums">{formatMoney(e.tax_paise)}</TD><TD>v{e.config_version}</TD>
                </TR>
              ))}</TBody>
            </Table>
            <Pagination path="/finance/ledger" params={params} page={page} hasMore={res.data.has_more} shown={res.data.items.length} />
          </>
        )}
      </Card>
    </div>
  );
}
