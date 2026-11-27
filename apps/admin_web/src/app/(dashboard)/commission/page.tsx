import type { Metadata } from "next";
import Link from "next/link";
import { ActionButton, type Field } from "@/components/data/action-button";
import { CommissionTabs } from "@/components/data/commission-tabs";
import { FilterBar } from "@/components/data/filter-bar";
import { PageHeader } from "@/components/data/page-header";
import { StatusBadge } from "@/components/data/status-badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { hasPermission } from "@/lib/admin-access";
import { bpsHelp, type CommissionRule, type RulesResponse } from "@/lib/commission";
import { formatDateTime } from "@/lib/format";
import { one, type SearchParams } from "@/lib/query";
import type { Paged, VenueRow } from "@/lib/types";

export const metadata: Metadata = { title: "Commission" };
type Cat = { id: string; name: string; is_active: boolean };
const BACK = ["/commission", "/commission/history", "/finance"];
const WHEN: Field = { name: "effective_from", label: "Effective from (optional)", type: "datetime", help: "Empty = immediately. Cannot be in the past. It applies only to bookings made from this moment on; bookings already made keep their rate." };
const REASON: Field = { name: "reason", label: "Reason", type: "textarea", required: true, maxLength: 300, placeholder: "Why is this changing? It is kept in the permanent history." };
const PCT: Field = { name: "commission_bps", label: "Commission (basis points)", type: "number", required: true, min: 0, max: 10000, help: bpsHelp };

function RuleActions({ r, canManage, label }: { r: CommissionRule; canManage: boolean; label: string }) {
  if (!canManage || !r.current) return null;
  const on = r.current.is_active;
  return (
    <div className="flex flex-wrap gap-2">
      <ActionButton label="Change %" size="sm" title={`Change the percentage: ${label}`} path={`/admin/commission/rules/${r.id}/versions`} refresh={BACK} testId="rule-change"
        description="Adds a new version. Earlier versions, existing bookings and past earnings are never changed." fields={[{ ...PCT, defaultValue: r.current.commission_bps }, WHEN, REASON]} />
      <ActionButton label={on ? "Deactivate" : "Activate"} size="sm" danger={on} title={`${on ? "Deactivate" : "Activate"}: ${label}`} path={`/admin/commission/rules/${r.id}/versions`} fixed={{ is_active: !on }} refresh={BACK} testId="rule-toggle"
        description={on ? "New bookings will use the next rule in the priority order. Existing bookings keep their rate." : "New bookings will use this rule again."} fields={[WHEN, REASON]} />
    </div>
  );
}

function Status({ r }: { r: CommissionRule }) {
  return (
    <div className="space-y-1">
      <StatusBadge status={r.is_active_now ? "active" : "expired"} /><span className="ml-1 text-xs text-muted-foreground">{r.current ? (r.is_active_now ? "Active" : "Inactive") : "Not started"}</span>
      {r.pending.map((p) => <p key={p.id} className="text-xs text-muted-foreground" data-testid="pending-change">From {formatDateTime(p.effective_from)}: {p.is_active ? `${p.commission_pct}` : "deactivated"}</p>)}
    </div>
  );
}

export default async function CommissionPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const vq = one(params, "venue_q");
  const [rules, cats, found, canManage] = await Promise.all([
    safe(adminGet<RulesResponse>("/admin/commission/rules")),
    safe(adminGet<{ items: Cat[] }>("/admin/categories")),
    vq ? safe(adminGet<Paged<VenueRow>>("/admin/venues", { q: vq, limit: 10 })) : Promise.resolve(null),
    hasPermission("commission.manage"),
  ]);
  if (!rules.ok) return <ErrorState message={`Could not load commission rules (${rules.error.message}).`} />;
  const d = rules.data;
  const g = d.global;
  const activity = d.items.filter((r) => r.scope === "activity");
  const venue = d.items.filter((r) => r.scope === "venue");
  const taken = new Set(activity.map((r) => r.category_id));
  const freeCats = cats.ok ? cats.data.items.filter((c) => c.is_active && !taken.has(c.id)) : [];
  const venueTaken = new Set(venue.map((r) => r.venue_id));
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader title="Commission management" description="The percentage ZURUV keeps from each booking's court charge. Rules are versioned: a change only affects bookings made after it takes effect." />
      <CommissionTabs current="/commission" />

      <Alert variant="info" data-testid="priority-note">
        <p className="font-medium">Which rule applies? Exactly one per booking, in this order:</p>
        <ol className="mt-1 list-decimal pl-5">
          <li><strong>Venue-specific</strong> rule, if the venue has an active one.</li>
          <li><strong>Activity-specific</strong> rule for the venue&apos;s sport. If a venue offers several sports that each have a rule, the booking is NOT given a rate and is not accrued until the client approves a tie-break (open decision).</li>
          <li><strong>Global default</strong>.</li>
        </ol>
        <p className="mt-2 text-xs">The rate is fixed on each booking when it is created and never recalculated. If no rule applies, the percentage of the approved <Link href="/finance/configs" className="underline">finance configuration</Link> is used. Nothing is recorded in the ledger until that configuration is approved (Q7/Q8).</p>
      </Alert>

      {d.ambiguous_venues.length > 0 && (
        <Alert variant="error" data-testid="ambiguous-venues">
          <p className="font-medium">Decision needed: {d.ambiguous_venues.length} venue(s) offer sports with different activity percentages.</p>
          <p className="text-sm">New bookings there get no commission rate and are not recorded in the ledger until the client approves a tie-break (or you give the venue its own rule): {d.ambiguous_venues.map((v) => `${v.venue_name} (${v.percentages.map((b) => `${b / 100}%`).join(" / ")})`).join(", ")}.</p>
        </Alert>
      )}

      <Card data-testid="global-rule">
        <CardHeader className="flex-row flex-wrap items-start justify-between gap-3">
          <div><CardTitle>Global default commission</CardTitle><CardDescription>Used when no venue or activity rule applies.</CardDescription></div>
          {canManage && !g && (
            <ActionButton label="Set global commission" variant="default" title="Set the global commission" path="/admin/commission/rules" fixed={{ scope: "global", is_active: true }} refresh={BACK} testId="global-create"
              fields={[PCT, WHEN, REASON]} />
          )}
          {g && <RuleActions r={g} canManage={canManage} label="global default" />}
        </CardHeader>
        <CardContent>
          {!g || !g.current ? <p className="text-sm text-muted-foreground">No global commission is set. Without one, bookings use the approved finance configuration&apos;s percentage.</p> : (
            <div className="flex flex-wrap items-baseline gap-x-8 gap-y-2">
              <p className="text-4xl font-semibold tabular-nums" data-testid="global-pct">{g.current.commission_pct}</p>
              <div className="text-sm"><Status r={g} /></div>
              <p className="text-sm text-muted-foreground">Effective since {formatDateTime(g.current.effective_from)} · version {g.current.version}</p>
            </div>
          )}
        </CardContent>
      </Card>

      <Card data-testid="activity-rules">
        <CardHeader className="flex-row flex-wrap items-start justify-between gap-3">
          <div><CardTitle>Activity-wise commission</CardTitle><CardDescription>A different percentage for individual sports.</CardDescription></div>
          {canManage && (
            <ActionButton label="Add activity rule" variant="default" title="Commission for an activity" path="/admin/commission/rules" fixed={{ scope: "activity", is_active: true }} refresh={BACK} testId="activity-create" disabled={freeCats.length === 0} disabledReason="Every active sport already has a rule."
              fields={[{ name: "category_id", label: "Sport / activity", type: "select", required: true, options: freeCats.map((c) => ({ value: c.id, label: c.name })) }, PCT, WHEN, REASON]} />
          )}
        </CardHeader>
        {activity.length === 0 ? <EmptyState title="No activity rules" description="Every sport uses the global default." /> : (
          <Table>
            <THead><TR><TH>Activity</TH><TH>Commission</TH><TH>Status</TH><TH>Since</TH><TH>Actions</TH></TR></THead>
            <TBody>{activity.map((r) => (
              <TR key={r.id}><TD className="font-medium">{r.category_name}</TD><TD className="tabular-nums">{r.current?.commission_pct}</TD><TD><Status r={r} /></TD><TD className="whitespace-nowrap text-xs">{formatDateTime(r.current?.effective_from)}</TD>
                <TD><div className="flex flex-wrap items-center gap-2"><RuleActions r={r} canManage={canManage} label={r.category_name ?? ""} /><Link href={`/commission/history?category_id=${r.category_id}`} className="text-xs text-primary hover:underline">History</Link></div></TD></TR>
            ))}</TBody>
          </Table>
        )}
      </Card>

      <Card data-testid="venue-rules">
        <CardHeader><CardTitle>Venue-wise commission</CardTitle><CardDescription>An individual percentage for a selected venue. Search for a venue, then set its commission.</CardDescription></CardHeader>
        <FilterBar path="/commission" params={params} fields={[{ kind: "search", name: "venue_q", placeholder: "Search venues by name…" }]} />
        {found && (!found.ok ? <div className="p-4"><ErrorState message={`Venue search failed (${found.error.message}).`} /></div> : found.data.items.length === 0 ? <EmptyState title="No venue matches" /> : (
          <Table>
            <THead><TR><TH>Search results</TH><TH>Owner</TH><TH>Sports</TH><TH>Action</TH></TR></THead>
            <TBody>{found.data.items.map((v) => (
              <TR key={v.id}><TD className="font-medium">{v.name}</TD><TD>{v.business_name || v.owner_name}</TD><TD className="text-xs">{v.categories.join(", ")}</TD>
                <TD>{venueTaken.has(v.id) ? <span className="text-xs text-muted-foreground">Has a rule (see below)</span> : canManage ? (
                  <ActionButton label="Set commission" size="sm" title={`Commission for ${v.name}`} path="/admin/commission/rules" fixed={{ scope: "venue", venue_id: v.id, is_active: true }} refresh={BACK} testId="venue-create" fields={[PCT, WHEN, REASON]} />
                ) : null}</TD></TR>
            ))}</TBody>
          </Table>
        ))}
        {venue.length === 0 ? <EmptyState title="No venue rules" description="Search above to give a venue its own percentage." /> : (
          <Table>
            <THead><TR><TH>Venue</TH><TH>Commission</TH><TH>Status</TH><TH>Since</TH><TH>Actions</TH></TR></THead>
            <TBody>{venue.map((r) => (
              <TR key={r.id}><TD className="font-medium">{r.venue_name}</TD><TD className="tabular-nums">{r.current?.commission_pct}</TD><TD><Status r={r} /></TD><TD className="whitespace-nowrap text-xs">{formatDateTime(r.current?.effective_from)}</TD>
                <TD><div className="flex flex-wrap items-center gap-2"><RuleActions r={r} canManage={canManage} label={r.venue_name ?? ""} /><Link href={`/commission/history?venue_id=${r.venue_id}`} className="text-xs text-primary hover:underline">History</Link></div></TD></TR>
            ))}</TBody>
          </Table>
        )}
      </Card>
    </div>
  );
}
