import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ActionButton } from "@/components/data/action-button";
import { Detail, DetailGrid, Mono } from "@/components/data/detail";
import { PageHeader } from "@/components/data/page-header";
import { StatusBadge } from "@/components/data/status-badge";
import { ErrorState } from "@/components/data/states";
import { Alert } from "@/components/ui/alert";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { adminGet, safe } from "@/lib/admin-api";
import { hasPermission } from "@/lib/admin-access";
import { formatDateTime, formatMoney, titleCase } from "@/lib/format";
import type { Row } from "@/lib/types";

export const metadata: Metadata = { title: "Refund" };

export default async function RefundPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [res, can] = await Promise.all([safe(adminGet<Row>(`/admin/refunds/${encodeURIComponent(id)}`)), hasPermission("refunds.manage")]);
  if (!res.ok) {
    if (res.error.status === 404 || res.error.status === 422) notFound();
    return <ErrorState message={`Could not load this refund (${res.error.message}).`} />;
  }
  const r = res.data as Record<string, string | number | null>;
  const unsettled = ["requested", "pending", "uncertain"].includes(String(r.status));
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader title={`Refund ${String(r.id).slice(0, 8)}`} description={`${r.booking_code} · ${r.venue_name}`} actions={<>
        <StatusBadge status={String(r.status)} />
        {can && unsettled && <ActionButton label="Check with Razorpay" title="Ask Razorpay what happened to this refund" path={`/admin/refunds/${r.id}/reconcile`} variant="default" refresh={[`/refunds/${r.id}`, "/refunds"]} testId="refund-reconcile"
          description="Looks the refund up at Razorpay and applies the real result. If Razorpay has no record, the original request is re-sent with the same idempotency key, so it can never be refunded twice." success="Checked. The status now reflects Razorpay." />}
      </>} />
      {r.status === "uncertain" && <Alert data-testid="uncertain-note">The gateway did not confirm in time. The refundable balance stays locked until this is checked.</Alert>}
      {r.failure_reason && <Alert>Failure: {r.failure_reason}</Alert>}
      <Card>
        <CardHeader><CardTitle>Details</CardTitle></CardHeader>
        <DetailGrid>
          <Detail label="Amount">{formatMoney(Number(r.amount_paise))}</Detail>
          <Detail label="Source">{r.source === "gateway" ? "Started in the Razorpay dashboard" : "Started here by an administrator"}</Detail>
          <Detail label="Booking"><Link href={`/bookings/${r.booking_id}`} className="text-primary hover:underline">{r.booking_code}</Link></Detail>
          <Detail label="Payment"><Link href={`/payments/${r.payment_id}`} className="text-primary hover:underline"><Mono>{String(r.payment_id).slice(0, 8)}</Mono></Link></Detail>
          <Detail label="Razorpay refund"><Mono>{r.provider_refund_id ?? "—"}</Mono></Detail>
          <Detail label="Razorpay payment"><Mono>{r.razorpay_payment_id ?? "—"}</Mono></Detail>
          <Detail label="Created">{formatDateTime(String(r.created_at))}</Detail>
          <Detail label="Processed">{formatDateTime(r.processed_at as string | null)}</Detail>
          <Detail label="Dispute">{r.dispute_id ? <Link href={`/disputes/${r.dispute_id}`} className="text-primary hover:underline">View dispute</Link> : "—"}</Detail>
          <div className="sm:col-span-2 lg:col-span-3"><Detail label="Reason">{r.reason}</Detail></div>
        </DetailGrid>
      </Card>
      <p className="text-xs text-muted-foreground">Status “{titleCase(String(r.status))}”. Every change is in the <Link href={`/audit?entity_type=refund&entity_id=${r.id}`} className="text-primary underline">audit log</Link>.</p>
    </div>
  );
}
