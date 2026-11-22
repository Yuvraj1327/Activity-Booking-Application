import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ActionButton, OPTIONAL_REASON, REASON } from "@/components/data/action-button";
import { AccountHistory } from "@/components/data/account-history";
import { BookingHistory } from "@/components/data/booking-history";
import { Detail, DetailGrid } from "@/components/data/detail";
import { PageHeader } from "@/components/data/page-header";
import { StatCard } from "@/components/data/stat-card";
import { StatusBadge } from "@/components/data/status-badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { StatusControl } from "@/components/data/status-control";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { hasPermission } from "@/lib/admin-access";
import { formatDate, formatDateTime, formatMoney, titleCase } from "@/lib/format";
import type { SearchParams } from "@/lib/query";
import type { Cursor, OwnerDetail, Row } from "@/lib/types";

export const metadata: Metadata = { title: "Owner" };

type Kyc = {
  kyc_status: string; kyc_note: string | null; kyc_reviewed_at: string | null;
  documents: { id: string; doc_type: string; original_filename: string | null; content_type: string; byte_size: number; status: string; rejection_reason: string | null; created_at: string; reviewed_at: string | null }[];
};
type Payouts = { balance: { available: boolean; reason?: string; earned_paise?: number; paid_paise?: number; reserved_paise?: number; payable_paise?: number } } & Cursor<Row>;

export default async function OwnerPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<SearchParams> }) {
  const { id } = await params;
  const sp = await searchParams;
  const [canManage, canKyc, canFinance] = await Promise.all([hasPermission("owners.manage"), hasPermission("kyc.review"), hasPermission("finance.view")]);
  const [res, kyc, payouts] = await Promise.all([
    safe(adminGet<OwnerDetail>(`/admin/owners/${encodeURIComponent(id)}`)),
    canKyc ? safe(adminGet<Kyc>(`/admin/owners/${encodeURIComponent(id)}/kyc`)) : Promise.resolve(null),
    canFinance ? safe(adminGet<Payouts>(`/admin/owners/${encodeURIComponent(id)}/payouts`, { limit: 10 })) : Promise.resolve(null),
  ]);
  if (!res.ok) {
    if (res.error.status === 404 || res.error.status === 422) notFound();
    return <ErrorState message={`Could not load this owner (${res.error.message}).`} />;
  }
  const o = res.data;
  const back = [`/owners/${o.id}`];
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader
        title={o.full_name}
        description={o.business_name}
        actions={<><StatusBadge status={o.status} /><span title="Business verification (KYC)"><StatusBadge status={o.kyc_status} /></span>{canManage && <StatusControl role="owner" id={o.id} name={o.full_name} status={o.status} />}</>}
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Venues" value={String(o.venues.length)} hint={`${o.verified_venues} verified`} />
        <StatCard label="Bookings" value={String(o.bookings_count)} hint={`${o.confirmed_count} confirmed`} />
        <StatCard label="Gross paid" value={formatMoney(o.gross_paid_paise)} hint={`Captured payments, before any deduction · ${formatMoney(o.refunds_paise)} refunded`} />
        <StatCard label="Verification (KYC)" value={titleCase(o.kyc_status)} hint={o.pending_kyc_documents ? `${o.pending_kyc_documents} document(s) waiting for review` : undefined} tone={o.kyc_status === "verified" ? "success" : o.pending_kyc_documents ? "warning" : "primary"} />
      </div>
      <Card>
        <CardHeader><CardTitle>Profile and contact</CardTitle></CardHeader>
        <DetailGrid>
          <Detail label="E-mail">{o.email}</Detail>
          <Detail label="Phone">{o.phone}</Detail>
          <Detail label="Registered">{formatDateTime(o.created_at)}</Detail>
          <Detail label="Business phone">{o.business_phone}</Detail>
          <Detail label="Business e-mail">{o.business_email}</Detail>
          <Detail label="Business address">{o.business_address}</Detail>
        </DetailGrid>
      </Card>

      {kyc && (
        <Card id="kyc" data-testid="kyc-panel">
          <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
            <CardTitle>Verification documents (KYC)</CardTitle>
            {kyc.ok && canKyc && (
              <div className="flex gap-2">
                <ActionButton label="Verify owner" title="Verify this owner?" path={`/admin/owners/${o.id}/kyc/decision`} fixed={{ decision: "verified" }} fields={[OPTIONAL_REASON]} variant="default" refresh={back} testId="kyc-verify"
                  description="Every document must be reviewed first and at least one approved." success="Owner verified." />
                <ActionButton label="Reject KYC" title="Reject this owner's verification?" path={`/admin/owners/${o.id}/kyc/decision`} fixed={{ decision: "rejected" }} fields={[REASON]} danger refresh={back} testId="kyc-reject"
                  description="The owner is told the reason and can upload new documents." />
              </div>
            )}
          </CardHeader>
          {!kyc.ok ? <p className="px-6 pb-6 text-sm text-muted-foreground">Documents are not available ({kyc.error.message}).</p> : kyc.data.documents.length === 0 ? (
            <EmptyState title="No documents submitted" description="The owner uploads documents from the venue-owner app." />
          ) : (
            <Table>
              <THead><TR><TH>Document</TH><TH>File</TH><TH>Submitted</TH><TH>Status</TH><TH>Review</TH></TR></THead>
              <TBody>{kyc.data.documents.map((d) => (
                <TR key={d.id}>
                  <TD className="font-medium">{titleCase(d.doc_type)}</TD>
                  <TD><a href={`/api/kyc/${d.id}`} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline" data-testid="kyc-view">View</a> <span className="text-xs text-muted-foreground">{d.content_type.split("/")[1].toUpperCase()} · {(d.byte_size / 1024).toFixed(0)} KB</span></TD>
                  <TD className="whitespace-nowrap text-xs">{formatDateTime(d.created_at)}</TD>
                  <TD><StatusBadge status={d.status} />{d.rejection_reason && <p className="mt-1 max-w-xs text-xs text-muted-foreground">“{d.rejection_reason}”</p>}</TD>
                  <TD>{d.status === "pending" ? (
                    <div className="flex gap-2">
                      <ActionButton label="Approve" title="Approve this document?" path={`/admin/kyc/documents/${d.id}/review`} fixed={{ decision: "approved" }} refresh={back} success="Document approved." />
                      <ActionButton label="Reject" title="Reject this document" path={`/admin/kyc/documents/${d.id}/review`} fixed={{ decision: "rejected" }} fields={[REASON]} danger refresh={back} description="The owner sees this reason." />
                    </div>
                  ) : <span className="text-xs text-muted-foreground">{formatDateTime(d.reviewed_at)}</span>}</TD>
                </TR>
              ))}</TBody>
            </Table>
          )}
          {kyc.ok && kyc.data.kyc_note && <p className="border-t border-border px-6 py-3 text-sm text-muted-foreground">Last decision note: {kyc.data.kyc_note}</p>}
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>Venues</CardTitle></CardHeader>
        {o.venues.length === 0 ? <EmptyState title="No venues yet" /> : (
          <Table>
            <THead><TR><TH>Venue</TH><TH>City</TH><TH>Status</TH><TH className="text-right">Bookings</TH><TH>Created</TH></TR></THead>
            <TBody>{o.venues.map((v) => (
              <TR key={v.id}>
                <TD><Link href={`/venues/${v.id}`} className="font-medium text-primary hover:underline">{v.name}</Link></TD>
                <TD>{v.city ?? "—"}</TD><TD><StatusBadge status={v.status} /></TD>
                <TD className="text-right tabular-nums">{v.confirmed_count}/{v.bookings_count}</TD><TD>{formatDate(v.created_at)}</TD>
              </TR>
            ))}</TBody>
          </Table>
        )}
      </Card>

      {payouts && (
        <Card id="payouts" data-testid="payout-history">
          <CardHeader className="flex-row items-center justify-between"><CardTitle>Payout history</CardTitle><Link href={`/payouts?owner_id=${o.id}`} className="text-sm text-primary hover:underline">Manage payouts</Link></CardHeader>
          {!payouts.ok ? <p className="px-6 pb-6 text-sm text-muted-foreground">Payouts are not available ({payouts.error.message}).</p> : (
            <>
              <p className="px-6 pb-3 text-sm text-muted-foreground">
                {payouts.data.balance.available
                  ? `Earned ${formatMoney(payouts.data.balance.earned_paise)} · paid ${formatMoney(payouts.data.balance.paid_paise)} · reserved ${formatMoney(payouts.data.balance.reserved_paise)} · payable ${formatMoney(payouts.data.balance.payable_paise)}`
                  : `Earnings are not available: ${payouts.data.balance.reason}`}
              </p>
              {payouts.data.items.length === 0 ? <EmptyState title="No payouts recorded" description="Payout records are created once payouts are approved and enabled." /> : (
                <Table>
                  <THead><TR><TH>Created</TH><TH className="text-right">Amount</TH><TH>Status</TH><TH>Reference</TH><TH>Paid</TH></TR></THead>
                  <TBody>{payouts.data.items.map((p) => (
                    <TR key={p.id}><TD className="whitespace-nowrap text-xs">{formatDateTime(String(p.created_at))}</TD><TD className="text-right tabular-nums">{formatMoney(Number(p.amount_paise))}</TD><TD><StatusBadge status={String(p.status)} /></TD><TD className="font-mono text-xs">{String(p.reference ?? "—")}</TD><TD className="text-xs">{formatDateTime(p.paid_at as string | null)}</TD></TR>
                  ))}</TBody>
                </Table>
              )}
            </>
          )}
        </Card>
      )}

      <BookingHistory filter="owner_id" id={o.id} path={`/owners/${o.id}`} params={sp} title="Booking history at this owner's venues" />
      <AccountHistory kind="owners" id={o.id} />
    </div>
  );
}
