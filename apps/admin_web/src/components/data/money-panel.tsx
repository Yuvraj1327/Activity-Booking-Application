import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatMoney } from "@/lib/format";
import type { Money } from "@/lib/types";

/** The five money figures are different things and are never merged or relabelled. */
export function MoneyPanel({ money }: { money: Money }) {
  const row = "flex items-start justify-between gap-4 border-b border-border py-3 last:border-0";
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
            ["Platform revenue", money.platform_revenue],
            ["Owner earnings", money.owner_earnings],
            ["Refunds", money.refunds],
          ] as const).map(([label, u]) => (
            <div key={label} className={row}>
              <dt><p className="font-medium">{label}</p><p className="text-xs text-muted-foreground">Waiting for an approved rule: {u.depends_on}</p></dt>
              <dd className="text-sm text-muted-foreground" data-testid={`money-${label.toLowerCase().replace(" ", "-")}`}>Not available</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}
