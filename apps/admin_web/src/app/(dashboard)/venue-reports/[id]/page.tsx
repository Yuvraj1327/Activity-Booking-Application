import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ActionButton } from "@/components/data/action-button";
import { Detail, DetailGrid } from "@/components/data/detail";
import { PageHeader } from "@/components/data/page-header";
import { StatusBadge } from "@/components/data/status-badge";
import { ErrorState } from "@/components/data/states";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { adminGet, safe } from "@/lib/admin-api";
import { hasPermission } from "@/lib/admin-access";
import { formatDateTime, titleCase } from "@/lib/format";

export const metadata: Metadata = { title: "Venue report" };

type R = { id: string; venue_id: string; venue_name: string; venue_status: string | null; reporter_name: string | null; reason: string; details: string | null; status: string; resolution_note: string | null; resolved_at: string | null; created_at: string; other_reports_on_venue: number };

export default async function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [res, can] = await Promise.all([safe(adminGet<R>(`/admin/venue-reports/${encodeURIComponent(id)}`)), hasPermission("venues.moderate")]);
  if (!res.ok) {
    if (res.error.status === 404 || res.error.status === 422) notFound();
    return <ErrorState message={`Could not load this report (${res.error.message}).`} />;
  }
  const r = res.data;
  const open = r.status === "open" || r.status === "reviewing";
  const back = [`/venue-reports/${r.id}`, "/venue-reports"];
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader title={`Report: ${titleCase(r.reason)}`} description={r.venue_name} actions={<><StatusBadge status={r.status} /><Link href={`/venues/${r.venue_id}`} className="text-sm text-primary hover:underline">Open venue</Link></>} />
      <Card>
        <CardHeader><CardTitle>Details</CardTitle></CardHeader>
        <DetailGrid>
          <Detail label="Venue">{r.venue_name} {r.venue_status && <StatusBadge status={r.venue_status} />}</Detail>
          <Detail label="Reported by">{r.reporter_name}</Detail>
          <Detail label="Received">{formatDateTime(r.created_at)}</Detail>
          <Detail label="Other reports on this venue">{r.other_reports_on_venue}</Detail>
          <div className="sm:col-span-2 lg:col-span-3"><Detail label="What the customer wrote">{r.details || "No details given."}</Detail></div>
          {r.resolution_note && <div className="sm:col-span-2 lg:col-span-3"><Detail label={`Resolution (${formatDateTime(r.resolved_at)})`}>{r.resolution_note}</Detail></div>}
        </DetailGrid>
      </Card>
      {can && open && (
        <Card><div className="flex flex-wrap gap-2 p-4">
          {r.status === "open" && <ActionButton label="Start review" path={`/admin/venue-reports/${r.id}`} method="PATCH" fixed={{ status: "reviewing" }} refresh={back} success="Report is under review." />}
          <ActionButton label="Dismiss" title="Dismiss this report" method="PATCH" path={`/admin/venue-reports/${r.id}`} fixed={{ status: "dismissed" }} fields={[{ name: "note", label: "Why is no action needed?", type: "textarea", required: true, maxLength: 300 }]} refresh={back} />
          <ActionButton label="Action taken" title="Close as action taken" method="PATCH" path={`/admin/venue-reports/${r.id}`} fixed={{ status: "action_taken" }} fields={[{ name: "note", label: "What was done?", type: "textarea", required: true, maxLength: 300, help: "For example: venue suspended, owner warned." }]} refresh={back} variant="default" />
        </div></Card>
      )}
    </div>
  );
}
