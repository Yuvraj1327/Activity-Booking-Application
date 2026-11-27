import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { adminGet, safe } from "@/lib/admin-api";
import { SCOPE_LABEL, type BookingCommission } from "@/lib/commission";
import { formatDateTime, formatMoney } from "@/lib/format";

/** The commission rate fixed for one booking, and how the ledger applied it. Read-only. */
export async function CommissionPanel({ bookingId }: { bookingId: string }) {
  const res = await safe(adminGet<BookingCommission>(`/admin/commission/bookings/${encodeURIComponent(bookingId)}`));
  if (!res.ok) return null; // no permission or not found: the rest of the page already explains it
  const { snapshot: s, calculation: c, net, note } = res.data;
  const row = "flex justify-between gap-4";
  return (
    <Card data-testid="commission-panel">
      <CardHeader><CardTitle>Commission</CardTitle></CardHeader>
      <CardContent className="space-y-3 text-sm">
        {!s ? <p className="text-muted-foreground">No commission snapshot yet. It is stored the first time this booking is accrued.</p> : (
          <dl className="grid gap-2 sm:max-w-lg">
            <div className={row}><dt className="text-muted-foreground">Rule applied</dt><dd>{SCOPE_LABEL[s.scope] ?? s.scope}{s.rule_version ? ` · version ${s.rule_version}` : ""}</dd></div>
            <div className={row}><dt className="text-muted-foreground">Percentage fixed at booking</dt><dd className="font-medium">{s.commission_pct ?? "Finance configuration percentage"}</dd></div>
            <div className={row}><dt className="text-muted-foreground">Fixed on</dt><dd>{formatDateTime(s.effective_at)}</dd></div>
          </dl>
        )}
        {c ? (
          <dl className="grid gap-2 border-t border-border pt-3 sm:max-w-lg" data-testid="commission-calc">
            <div className={row}><dt className="text-muted-foreground">Gross paid</dt><dd className="tabular-nums">{formatMoney(c.gross_paise)}</dd></div>
            <div className={row}><dt className="text-muted-foreground">Commission base</dt><dd className="tabular-nums">{c.commission_base_paise == null ? "—" : formatMoney(c.commission_base_paise)}</dd></div>
            <div className={row}><dt className="text-muted-foreground">Commission ({c.commission_pct ?? "—"})</dt><dd className="tabular-nums">{formatMoney(c.commission_paise)}</dd></div>
            <div className={`${row} font-semibold`}><dt>Owner net payable</dt><dd className="tabular-nums">{formatMoney(c.owner_net_paise)}</dd></div>
            {net.refunded_paise > 0 && <div className={row}><dt className="text-muted-foreground">After {formatMoney(net.refunded_paise)} refunded</dt><dd className="tabular-nums">commission {formatMoney(net.commission_paise)} · owner {formatMoney(net.owner_net_paise)}</dd></div>}
          </dl>
        ) : note && <p className="text-muted-foreground">{note}</p>}
        <p className="text-xs text-muted-foreground">Rule history: <Link href="/commission/history" className="text-primary hover:underline">Commission history</Link>. Net payable is a ledger record, not a completed transfer.</p>
      </CardContent>
    </Card>
  );
}
