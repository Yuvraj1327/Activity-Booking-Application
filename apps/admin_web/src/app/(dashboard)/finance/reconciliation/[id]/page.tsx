import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Detail, DetailGrid, Mono } from "@/components/data/detail";
import { FinanceTabs } from "@/components/data/finance-tabs";
import { PageHeader } from "@/components/data/page-header";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Alert } from "@/components/ui/alert";
import { buttonLink } from "@/components/ui/button-link";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDateTime, formatMoney, titleCase } from "@/lib/format";

export const metadata: Metadata = { title: "Reconciliation run" };
type Run = { id: string; period_from: string; period_to: string; gateway_checked: boolean; gateway_note: string | null; mismatch_count: number; created_at: string; summary: Record<string, number>;
  items: { id: string; kind: string; payment_id: string | null; provider_payment_id: string | null; expected_paise: number | null; actual_paise: number | null; detail: string | null }[] };

export default async function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const res = await safe(adminGet<Run>(`/admin/finance/reconciliation/${encodeURIComponent(id)}`));
  if (!res.ok) {
    if (res.error.status === 404 || res.error.status === 422) notFound();
    return <ErrorState message={`Could not load this run (${res.error.message}).`} />;
  }
  const r = res.data;
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader title={`Reconciliation ${r.period_from} → ${r.period_to}`} description={`Run ${formatDateTime(r.created_at)}`} actions={<a className={buttonLink} href={`/api/exports/reconciliation?run_id=${r.id}`} download>Export mismatches (CSV)</a>} />
      <FinanceTabs current="/finance/reconciliation" />
      {!r.gateway_checked && <Alert data-testid="gateway-skipped">Razorpay was not compared: {r.gateway_note}</Alert>}
      <Card><CardHeader><CardTitle>Totals</CardTitle></CardHeader><DetailGrid>
        <Detail label="Payments in period">{r.summary.db_payments}</Detail><Detail label="Captured in our records">{r.summary.db_captured} ({formatMoney(r.summary.db_captured_paise)})</Detail>
        <Detail label="Captured at Razorpay">{r.gateway_checked ? `${r.summary.gateway_captured} (${formatMoney(r.summary.gateway_captured_paise)})` : "Not compared"}</Detail><Detail label="Mismatches">{r.mismatch_count}</Detail>
      </DetailGrid></Card>
      <Card data-testid="mismatches">
        <CardHeader><CardTitle>Mismatches</CardTitle></CardHeader>
        {r.items.length === 0 ? <EmptyState title="Everything matches" /> : (
          <Table>
            <THead><TR><TH>Kind</TH><TH>Payment</TH><TH className="text-right">Expected</TH><TH className="text-right">Found</TH><TH>Detail</TH></TR></THead>
            <TBody>{r.items.map((i) => (
              <TR key={i.id}><TD className="font-medium">{titleCase(i.kind)}</TD>
                <TD>{i.payment_id ? <Link href={`/payments/${i.payment_id}`} className="text-primary hover:underline"><Mono>{i.provider_payment_id ?? i.payment_id.slice(0, 8)}</Mono></Link> : <Mono>{i.provider_payment_id ?? "—"}</Mono>}</TD>
                <TD className="text-right tabular-nums">{i.expected_paise === null ? "—" : formatMoney(i.expected_paise)}</TD><TD className="text-right tabular-nums">{i.actual_paise === null ? "—" : formatMoney(i.actual_paise)}</TD><TD className="max-w-md text-xs text-muted-foreground">{i.detail}</TD></TR>
            ))}</TBody>
          </Table>
        )}
      </Card>
    </div>
  );
}
