import { Download } from "lucide-react";
import { buttonLink } from "@/components/ui/button-link";

export function ExportButton({ kind, query = {}, label = "Export CSV" }: { kind: "bookings" | "payments" | "customers" | "owners" | "refunds" | "ledger" | "payouts" | "analytics" | "reconciliation"; query?: Record<string, string | undefined>; label?: string }) {
  const qs = new URLSearchParams(Object.entries(query).filter(([, v]) => v) as [string, string][]).toString();
  return (
    <a href={`/api/exports/${kind}${qs ? `?${qs}` : ""}`} download className={buttonLink} data-testid={`export-${kind}`}>
      <Download className="size-4" aria-hidden /> {label}
    </a>
  );
}
