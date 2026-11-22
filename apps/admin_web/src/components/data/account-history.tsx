import { EmptyState } from "@/components/data/states";
import { StatusBadge } from "@/components/data/status-badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDateTime } from "@/lib/format";
import type { AuditRow, Paged } from "@/lib/types";

type Meta = { before?: Record<string, unknown>; after?: Record<string, unknown>; reason?: string };

/** What administrators have done to this account: suspensions, reinstatements, verification decisions, with the reason. */
export async function AccountHistory({ kind, id }: { kind: "customers" | "owners"; id: string }) {
  const res = await safe(adminGet<Paged<AuditRow>>(`/admin/${kind}/${id}/history`, { limit: 20 }));
  return (
    <Card id="history">
      <CardHeader><CardTitle>Account action history</CardTitle></CardHeader>
      {!res.ok ? <p className="px-6 pb-6 text-sm text-muted-foreground">History is not available ({res.error.message}).</p> : res.data.items.length === 0 ? <EmptyState title="No administrator actions yet" /> : (
        <ol className="divide-y divide-border">
          {res.data.items.map((a) => {
            const m = a.metadata as Meta;
            const from = m.before ? Object.values(m.before).join(", ") : null;
            const to = m.after ? Object.values(m.after).join(", ") : null;
            return (
              <li key={a.id} className="flex flex-wrap items-start justify-between gap-2 px-6 py-3 text-sm">
                <div>
                  <p className="font-medium">{a.action.replace("admin.", "").replace(/_/g, " ")}{from && to && <> · <span className="text-muted-foreground">{from}</span> → {to === "suspended" ? <StatusBadge status="suspended" /> : to === "active" ? <StatusBadge status="active" /> : to}</>}</p>
                  {m.reason && <p className="text-muted-foreground">“{m.reason}”</p>}
                </div>
                <p className="text-xs text-muted-foreground">{a.actor_name ?? "system"} · {formatDateTime(a.created_at)}</p>
              </li>
            );
          })}
        </ol>
      )}
    </Card>
  );
}
