import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatMoney } from "@/lib/format";
import type { Figure, Money, Unavailable } from "@/lib/types";

function Value({ f, testId }: { f: Figure | Unavailable | null | undefined; testId: string }) {
  if (f && f.available) return <dd className="font-semibold" data-testid={testId}>{formatMoney(f.amount_paise)}</dd>;
  return <dd className="text-sm text-muted-foreground" data-testid={testId}>Not available</dd>;
}

/** The money figures are different things and are never merged or relabelled. A figure only appears when real data backs it. */
export function MoneyPanel({ money }: { money: Money }) {
  const row = "flex items-start justify-between gap-4 border-b border-border py-3 last:border-0";
  const waiting = (f: Figure | Unavailable | null | undefined) =>
    f && !f.available ? `Waiting for an approved rule: ${f.depends_on}` : f && f.available ? f.note : "";
  const cov = money.ledger_coverage;
  return (
    <Card data-testid="money-panel">
      <CardHeader>
        <CardTitle>Money, by definition</CardTitle>
        <CardDescription>Only figures backed by recorded data or an approved rule are shown.</CardDescription>
      </CardHeader>
      <CardContent>
        <dl>
          <div className={row}>
            <dt><p className="font-medium">Gross booking value</p><p className="text-xs text-muted-foreground">Total of confirmed or completed bookings made in this period</p></dt>
            <dd className="font-semibold" data-testid="money-gross">{formatMoney(money.gross_booking_value_paise, money.currency)}</dd>
          </div>
          <div className={row}>
            <dt><p className="font-medium">Successful payments</p><p className="text-xs text-muted-foreground">Captured by Razorpay, gross, before any deduction</p></dt>
            <dd className="font-semibold" data-testid="money-paid">{formatMoney(money.successful_payment_paise, money.currency)}</dd>
          </div>
          {([
            ["Platform revenue", money.platform_revenue, "platform-revenue"],
            ["Owner earnings", money.owner_earnings, "owner-earnings"],
            ["Tax collected", money.tax_collected, "tax-collected"],
            ["Refunds processed", money.refunds, "refunds"],
          ] as const).map(([label, f, id]) => (
            <div key={label} className={row}>
              <dt><p className="font-medium">{label}</p><p className="text-xs text-muted-foreground">{waiting(f)}</p></dt>
              <Value f={f} testId={`money-${id}`} />
            </div>
          ))}
        </dl>
        {cov && cov.without_ledger_entry > 0 && (
          <p className="mt-3 text-xs text-muted-foreground" data-testid="coverage-note">
            {cov.without_ledger_entry} of {cov.captured_payments} captured payments in this period are not in the ledger yet (captured before a rule was approved, or accrual has not run).
          </p>
        )}
      </CardContent>
    </Card>
  );
}
