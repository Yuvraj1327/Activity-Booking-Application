import type { Metadata } from "next";
import { CheckCircle2, XCircle } from "lucide-react";
import { PageHeader } from "@/components/data/page-header";
import { StatCard } from "@/components/data/stat-card";
import { ErrorState } from "@/components/data/states";
import { Alert } from "@/components/ui/alert";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDateTime, formatNumber } from "@/lib/format";

export const metadata: Metadata = { title: "System monitoring" };

type M = {
  generated_at: string;
  backend: { name: string; version: string; environment: string; started_at: string; uptime_seconds: number };
  database: { status: string; latency_ms: number | null };
  payment_gateway: { api_configured: boolean; webhook_configured: boolean; mode: string; expected_mode: string; mode_matches_environment: boolean | null; note: string };
  webhooks: { last_24h: Record<string, number>; last_received_at: string | null; rejected_total: number; payments_needing_review: number; stuck_open_payments: number; uncertain_refunds: number };
  background_jobs: { sweep_enabled: boolean; sweep_interval_seconds: number | null; last_run_at: string | null; last_run_ok: boolean | null; note: string };
  delivery: { push_pending: number; push_failed: number; email_queued: number; email_failed: number };
  warnings: string[];
  recent_log_events: { scope: string; counts: Record<string, number>; items: { at: string; level: string; logger: string; message: string }[] };
};

const Ok = ({ ok }: { ok: boolean | null }) => ok === null ? <span>—</span> : ok ? <CheckCircle2 className="inline size-4 text-success" aria-label="OK" /> : <XCircle className="inline size-4 text-destructive" aria-label="Problem" />;
const up = (s: number) => (s >= 86400 ? `${Math.floor(s / 86400)} d ` : "") + (s >= 3600 ? `${Math.floor((s % 86400) / 3600)} h ` : "") + `${Math.floor((s % 3600) / 60)} min`;

export default async function MonitoringPage() {
  const res = await safe(adminGet<M>("/admin/monitoring"));
  if (!res.ok) return <ErrorState message={`Could not load monitoring (${res.error.message}).`} />;
  const m = res.data;
  const g = m.payment_gateway;
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader title="System monitoring" description={`Live from the API at ${formatDateTime(m.generated_at)}. Only things the system can verify are shown; no secrets or private infrastructure details.`} />
      {m.warnings.length > 0 && (
        <Alert data-testid="warnings"><p className="font-medium">Needs attention</p><ul className="mt-1 list-disc pl-5">{m.warnings.map((w) => <li key={w}>{w}</li>)}</ul></Alert>
      )}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Backend" value={`v${m.backend.version}`} hint={`${m.backend.environment} · up ${up(m.backend.uptime_seconds)} (since last restart)`} />
        <StatCard label="Database" value={m.database.status === "ok" ? "Connected" : m.database.status.replace(/_/g, " ")} hint={m.database.latency_ms !== null ? `${m.database.latency_ms} ms` : undefined} tone={m.database.status === "ok" ? "success" : "danger"} />
        <StatCard label="Payment gateway" value={g.api_configured ? `Configured (${g.mode})` : "Not configured"} hint={g.mode_matches_environment === false ? `Expected ${g.expected_mode} keys here` : g.note} tone={g.api_configured && g.mode_matches_environment !== false ? "success" : "warning"} />
        <StatCard label="Webhook secret" value={g.webhook_configured ? "Configured" : "Missing"} hint={m.webhooks.last_received_at ? `Last event ${formatDateTime(m.webhooks.last_received_at)}` : "No webhook received yet"} tone={g.webhook_configured ? "success" : "danger"} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card data-testid="webhooks-card">
          <CardHeader><CardTitle>Payment webhooks</CardTitle></CardHeader>
          <dl className="space-y-2 px-6 pb-6 text-sm">
            <Row k="Events in the last 24 h" v={Object.entries(m.webhooks.last_24h).map(([o, n]) => `${o}: ${n}`).join(" · ") || "none"} />
            <Row k="Rejected events (all time)" v={formatNumber(m.webhooks.rejected_total)} bad={m.webhooks.rejected_total > 0} />
            <Row k="Payments needing review" v={formatNumber(m.webhooks.payments_needing_review)} bad={m.webhooks.payments_needing_review > 0} />
            <Row k="Open payments with no gateway result" v={formatNumber(m.webhooks.stuck_open_payments)} bad={m.webhooks.stuck_open_payments > 0} />
            <Row k="Refunds with an unknown result" v={formatNumber(m.webhooks.uncertain_refunds)} bad={m.webhooks.uncertain_refunds > 0} />
          </dl>
        </Card>
        <Card data-testid="jobs-card">
          <CardHeader><CardTitle>Background jobs and delivery</CardTitle></CardHeader>
          <dl className="space-y-2 px-6 pb-6 text-sm">
            <div className="flex justify-between gap-4"><dt className="text-muted-foreground">Housekeeping sweep</dt><dd>{m.background_jobs.sweep_enabled ? <>every {m.background_jobs.sweep_interval_seconds}s · {m.background_jobs.last_run_at ? <>last run {formatDateTime(m.background_jobs.last_run_at)} <Ok ok={m.background_jobs.last_run_ok} /></> : "has not run since the last restart"}</> : "Disabled"}</dd></div>
            <Row k="Push notifications queued / failed" v={`${m.delivery.push_pending} / ${m.delivery.push_failed}`} bad={m.delivery.push_failed > 0} />
            <Row k="E-mails queued / failed" v={`${m.delivery.email_queued} / ${m.delivery.email_failed}`} bad={m.delivery.email_failed > 0} />
            <p className="text-xs text-muted-foreground">{m.background_jobs.note}</p>
          </dl>
        </Card>
      </div>
      <Card data-testid="log-card">
        <CardHeader><CardTitle>Recent warnings and errors</CardTitle><p className="text-sm text-muted-foreground">{m.recent_log_events.scope}. Warnings: {m.recent_log_events.counts.WARNING ?? 0} · errors: {m.recent_log_events.counts.ERROR ?? 0}</p></CardHeader>
        {m.recent_log_events.items.length === 0 ? <p className="px-6 pb-6 text-sm text-muted-foreground">Nothing logged since this process started.</p> : (
          <Table>
            <THead><TR><TH>When</TH><TH>Level</TH><TH>Source</TH><TH>Message</TH></TR></THead>
            <TBody>{m.recent_log_events.items.map((e, i) => <TR key={i}><TD className="whitespace-nowrap text-xs">{formatDateTime(e.at)}</TD><TD>{e.level}</TD><TD className="font-mono text-xs">{e.logger}</TD><TD className="max-w-xl truncate text-xs">{e.message}</TD></TR>)}</TBody>
          </Table>
        )}
      </Card>
    </div>
  );
}

function Row({ k, v, bad }: { k: string; v: string; bad?: boolean }) {
  return <div className="flex justify-between gap-4"><dt className="text-muted-foreground">{k}</dt><dd className={bad ? "font-medium text-destructive" : ""}>{v}</dd></div>;
}
