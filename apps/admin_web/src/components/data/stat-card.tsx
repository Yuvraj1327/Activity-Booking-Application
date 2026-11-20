import { Sparkline } from "@/components/data/sparkline";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "primary",
  trend,
}: {
  label: string;
  value: string;
  hint?: string;
  icon?: React.ComponentType<{ className?: string }>;
  tone?: "primary" | "success" | "warning" | "danger";
  /** Real series for a small trend line (omit when there is none). */
  trend?: number[];
}) {
  const tones = { primary: "bg-primary-tint text-primary", success: "bg-success/10 text-success", warning: "bg-warning/15 text-warning-foreground", danger: "bg-destructive/10 text-destructive" };
  return (
    <Card className="relative overflow-hidden p-5" data-testid="stat-card">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="mt-2 truncate text-2xl font-semibold tracking-tight" data-testid="stat-value">{value}</p>
          {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
        </div>
        {Icon && (
          <span className={cn("flex size-10 shrink-0 items-center justify-center rounded-xl", tones[tone])}>
            <Icon className="size-5" aria-hidden />
          </span>
        )}
      </div>
      {trend && <Sparkline values={trend} className="pointer-events-none absolute bottom-3 right-4 h-9 w-24 text-primary" />}
    </Card>
  );
}
