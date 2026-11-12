import type { Metadata } from "next";
import Link from "next/link";
import { DateRangeFilter } from "@/components/data/date-range-filter";
import { MoneyPanel } from "@/components/data/money-panel";
import { PageHeader } from "@/components/data/page-header";
import { StatCard } from "@/components/data/stat-card";
import { ErrorState } from "@/components/data/states";
import { DonutChart, HBarChart, TrendChart } from "@/components/charts/charts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { adminGet, safe } from "@/lib/admin-api";
import { formatBucket, formatMoney, formatNumber, titleCase } from "@/lib/format";
import { href, one, resolveRange, type SearchParams } from "@/lib/query";
import type { BookingAnalytics, Granularity, PlatformAnalytics, RevenueAnalytics } from "@/lib/types";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Analytics" };

const TABS = [
  { key: "bookings", label: "Bookings" },
  { key: "revenue", label: "Transactions" },
  { key: "platform", label: "Platform" },
] as const;
const GRAN: Granularity[] = ["day", "week", "month"];

export default async function AnalyticsPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const range = resolveRange(params);
  const tab = TABS.find((t) => t.key === one(params, "tab"))?.key ?? "bookings";
  const g = (GRAN.find((x) => x === one(params, "granularity")) ?? "day") as Granularity;
  const query = { from: range.from, to: range.to, granularity: g };

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader title="Analytics" description="Aggregated in the database; the browser only receives the totals." />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="tablist" aria-label="Report" className="inline-flex rounded-lg border border-border bg-card p-1">
          {TABS.map((t) => (
            <Link key={t.key} role="tab" aria-selected={tab === t.key} href={href("/analytics", params, { tab: t.key })}
              className={cn("rounded-md px-4 py-1.5 text-sm", tab === t.key ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted")}>{t.label}</Link>
          ))}
        </div>
        <div role="group" aria-label="Group by" className="inline-flex rounded-lg border border-border bg-card p-1">
          {GRAN.map((x) => (
            <Link key={x} href={href("/analytics", params, { granularity: x })} aria-current={g === x ? "true" : undefined}
              className={cn("rounded-md px-3 py-1.5 text-sm capitalize", g === x ? "bg-primary-tint font-medium text-primary" : "text-muted-foreground hover:bg-muted")}>{x === "day" ? "Daily" : x === "week" ? "Weekly" : "Monthly"}</Link>
          ))}
        </div>
      </div>
      <DateRangeFilter path="/analytics" params={params} range={range} />
      {tab === "bookings" && <Bookings query={query} g={g} />}
      {tab === "revenue" && <Revenue query={query} g={g} />}
      {tab === "platform" && <Platform query={query} g={g} />}
    </div>
  );
}

type Q = { from: string; to: string; granularity: Granularity };

async function Bookings({ query, g }: { query: Q; g: Granularity }) {
  const res = await safe(adminGet<BookingAnalytics>("/admin/analytics/bookings", query));
  if (!res.ok) return <ErrorState message={`Could not load booking analytics (${res.error.message}).`} />;
  const a = res.data;
  const conf = a.series.reduce((s, b) => s + b.confirmed, 0);
  const canc = a.series.reduce((s, b) => s + b.cancelled, 0);
  const pend = a.series.reduce((s, b) => s + b.pending, 0);
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total bookings" value={formatNumber(a.total)} />
        <StatCard label="Confirmed" value={formatNumber(conf)} tone="success" />
        <StatCard label="Pending payment" value={formatNumber(pend)} tone="warning" />
        <StatCard label="Cancelled" value={formatNumber(canc)} tone="danger" />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader><CardTitle>Booking trend</CardTitle><CardDescription>Bookings created per {g}</CardDescription></CardHeader>
          <CardContent><TrendChart title="Booking trend" kind="bar" data={a.series.map((b) => ({ label: formatBucket(b.bucket, g), Confirmed: b.confirmed, Pending: b.pending, Cancelled: b.cancelled, Other: b.other }))}
            series={[{ key: "Confirmed", label: "Confirmed", color: 3 }, { key: "Pending", label: "Pending", color: 4 }, { key: "Cancelled", label: "Cancelled", color: 5 }, { key: "Other", label: "Other", color: 2 }]} /></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Status distribution</CardTitle></CardHeader>
          <CardContent><DonutChart title="Booking status distribution" data={a.status_distribution.map((s) => ({ name: titleCase(s.status), value: s.count }))} /></CardContent>
        </Card>
      </div>
    </div>
  );
}

async function Revenue({ query, g }: { query: Q; g: Granularity }) {
  const res = await safe(adminGet<RevenueAnalytics>("/admin/analytics/revenue", query));
  if (!res.ok) return <ErrorState message={`Could not load transaction analytics (${res.error.message}).`} />;
  const r = res.data;
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Recorded transactions" value={formatNumber(r.transactions_total)} />
        <StatCard label="Successful" value={formatNumber(r.captured_count)} hint={formatMoney(r.money.successful_payment_paise)} tone="success" />
        <StatCard label="Failed" value={formatNumber(r.failed_count)} tone="danger" />
        <StatCard label="Success rate" value={r.success_rate_percent === null ? "—" : `${r.success_rate_percent}%`} hint="Paid ÷ (paid + failed)" />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader><CardTitle>Successful payment amount</CardTitle><CardDescription>Captured, gross, per {g}</CardDescription></CardHeader>
          <CardContent><TrendChart title="Successful payment amount" kind="area" valueFormat="money" data={r.series.map((p) => ({ label: formatBucket(p.bucket, g), Captured: p.captured_paise }))} series={[{ key: "Captured", label: "Captured" }]} /></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Success vs failure</CardTitle><CardDescription>Transaction counts per {g}</CardDescription></CardHeader>
          <CardContent><TrendChart title="Payment success and failure" kind="bar" data={r.series.map((p) => ({ label: formatBucket(p.bucket, g), Successful: p.captured_count, Failed: p.failed_count }))} series={[{ key: "Successful", label: "Successful", color: 3 }, { key: "Failed", label: "Failed", color: 5 }]} /></CardContent>
        </Card>
      </div>
      <MoneyPanel money={r.money} />
    </div>
  );
}

async function Platform({ query, g }: { query: Q; g: Granularity }) {
  const res = await safe(adminGet<PlatformAnalytics>("/admin/analytics/platform", query));
  if (!res.ok) return <ErrorState message={`Could not load platform analytics (${res.error.message}).`} />;
  const a = res.data;
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="New customers" value={formatNumber(a.new_customers)} />
        <StatCard label="New owners" value={formatNumber(a.new_owners)} />
        <StatCard label="New venues" value={formatNumber(a.new_venues)} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Registrations</CardTitle><CardDescription>New accounts per {g}</CardDescription></CardHeader>
          <CardContent><TrendChart title="Registrations" kind="line" data={a.series.map((s) => ({ label: formatBucket(s.bucket, g), Customers: s.customers, Owners: s.owners }))} series={[{ key: "Customers", label: "Customers" }, { key: "Owners", label: "Owners", color: 3 }]} /></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Venue growth</CardTitle><CardDescription>Venues created per {g}</CardDescription></CardHeader>
          <CardContent><TrendChart title="Venue growth" kind="bar" data={a.series.map((s) => ({ label: formatBucket(s.bucket, g), Venues: s.venues_created }))} series={[{ key: "Venues", label: "Venues created", color: 1 }]} /></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Popular categories</CardTitle><CardDescription>Bookings by venue category</CardDescription></CardHeader>
          <CardContent><HBarChart title="Popular categories" data={a.popular_categories.map((c) => ({ name: c.category, value: c.bookings }))} /></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Most-booked venues</CardTitle></CardHeader>
          <CardContent><HBarChart title="Most booked venues" color={3} data={a.top_venues.map((v) => ({ name: v.name, value: v.bookings }))} /></CardContent>
        </Card>
      </div>
    </div>
  );
}
