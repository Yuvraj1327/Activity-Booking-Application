import type { Metadata } from "next";
import Link from "next/link";
import { ActionButton } from "@/components/data/action-button";
import { FinanceTabs } from "@/components/data/finance-tabs";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { StatusBadge } from "@/components/data/status-badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Alert } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { hasPermission } from "@/lib/admin-access";
import { formatDateTime } from "@/lib/format";
import { PAGE_SIZE, pageOf, todayIn, type SearchParams } from "@/lib/query";
import type { Cursor } from "@/lib/types";

export const metadata: Metadata = { title: "Reconciliation" };
type R = { id: string; period_from: string; period_to: string; gateway_checked: boolean; gateway_note: string | null; mismatch_count: number; created_at: string };

export default async function ReconciliationPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const { offset, page } = pageOf(params);
  const [res, can] = await Promise.all([safe(adminGet<Cursor<R> & { items: R[] }>("/admin/finance/reconciliation", { limit: PAGE_SIZE, offset })), hasPermission("finance.manage")]);
  const today = todayIn();
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader title="Financial reconciliation" description="Compares our payments, refunds and ledger with each other and with Razorpay. A run only reports; it never changes money."
        actions={can && <ActionButton label="Run reconciliation" title="Run a reconciliation" path="/admin/finance/reconciliation" variant="default" refresh={["/finance/reconciliation"]} testId="recon-run"
          description="Up to 93 days. If Razorpay cannot be reached the run says so and checks our own records only."
          fields={[{ name: "date_from", label: "From", type: "date", required: true, defaultValue: today }, { name: "date_to", label: "To", type: "date", required: true, defaultValue: today }]} />} />
      <FinanceTabs current="/finance/reconciliation" />
      <Card>
        {!res.ok ? <div className="p-4"><ErrorState message={`Could not load runs (${res.error.message}).`} /></div> : res.data.items.length === 0 ? <EmptyState title="No runs yet" /> : (
          <>
            <Table>
              <THead><TR><TH>Run</TH><TH>Period</TH><TH>Razorpay compared</TH><TH className="text-right">Mismatches</TH></TR></THead>
              <TBody>{res.data.items.map((r) => (
                <TR key={r.id}>
                  <TD><Link href={`/finance/reconciliation/${r.id}`} className="text-primary hover:underline">{formatDateTime(r.created_at)}</Link></TD><TD>{r.period_from} → {r.period_to}</TD>
                  <TD>{r.gateway_checked ? "Yes" : <span className="text-warning-foreground">No: {r.gateway_note}</span>}</TD>
                  <TD className="text-right"><StatusBadge status={r.mismatch_count === 0 ? "active" : "suspended"} /><span className="ml-1 tabular-nums">{r.mismatch_count}</span></TD>
                </TR>
              ))}</TBody>
            </Table>
            <Pagination path="/finance/reconciliation" params={params} page={page} hasMore={res.data.has_more} shown={res.data.items.length} />
          </>
        )}
      </Card>
      <Alert variant="info">A mismatch is a question, not a verdict. Fix the cause (for example reconcile a payment or refund), then run again.</Alert>
    </div>
  );
}
