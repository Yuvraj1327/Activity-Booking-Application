import Link from "next/link";
import { cn } from "@/lib/utils";

const TABS = [["/finance", "Overview"], ["/finance/configs", "Fees, tax & commission"], ["/finance/ledger", "Ledger"], ["/finance/reconciliation", "Reconciliation"], ["/payouts", "Owner payouts"]] as const;

export function FinanceTabs({ current }: { current: string }) {
  return (
    <nav aria-label="Finance sections" className="mb-5 inline-flex flex-wrap rounded-lg border border-border bg-card p-1">
      {TABS.map(([h, l]) => <Link key={h} href={h} aria-current={current === h ? "page" : undefined} className={cn("rounded-md px-3 py-1.5 text-sm", current === h ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted")}>{l}</Link>)}
    </nav>
  );
}
