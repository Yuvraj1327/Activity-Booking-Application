import Link from "next/link";
import { cn } from "@/lib/utils";

const TABS = [["/commission", "Rules"], ["/commission/history", "History"], ["/commission/report", "Reports"], ["/finance", "Finance"]] as const;

export function CommissionTabs({ current }: { current: string }) {
  return (
    <nav aria-label="Commission sections" className="mb-5 inline-flex flex-wrap rounded-lg border border-border bg-card p-1">
      {TABS.map(([h, l]) => <Link key={h} href={h} aria-current={current === h ? "page" : undefined} className={cn("rounded-md px-3 py-1.5 text-sm", current === h ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted")}>{l}</Link>)}
    </nav>
  );
}
