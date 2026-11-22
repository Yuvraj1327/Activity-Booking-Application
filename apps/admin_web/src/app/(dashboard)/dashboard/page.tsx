import type { Metadata } from "next";
import Link from "next/link";
import { AlertTriangle, ArrowRight, Wallet, BadgeCheck, CalendarCheck, CalendarClock, CalendarX2, CreditCard, MapPin, ShieldCheck, Store, Users } from "lucide-react";
import { BriefBookings } from "@/components/data/booking-table";
import { DateRangeFilter } from "@/components/data/date-range-filter";
import { MoneyPanel } from "@/components/data/money-panel";
import { DashboardHero } from "@/components/dashboard/hero";
import { StatCard } from "@/components/data/stat-card";
import { EmptyState, ErrorState } from "@/components/data/states";
import { TrendChart } from "@/components/charts/charts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { adminGet, safe } from "@/lib/admin-api";
import { formatBucket, formatDateTime, formatMoney, formatNumber, titleCase } from "@/lib/format";
import { resolveRange, type SearchParams } from "@/lib/query";
import type { Dashboard } from "@/lib/types";

export const metadata: Metadata = { title: "Dashboard" };

export default async function DashboardPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const range = resolveRange(params);
  const res = await safe(adminGet<Dashboard>("/admin/dashboard", { from: range.from, to: range.to }));

  return (
    <div className="mx-auto max-w-7xl">
      <h2 className="sr-only">Dashboard</h2>
      <div className="mb-6"><DashboardHero /></div>
      <div className="mb-6"><DateRangeFilter path="/dashboard" params={params} range={range} /></div>
      {!res.ok ? <ErrorState message={`Could not load the dashboard (${res.error.message}).`} /> : <Body d={res.data} />}
    </div>
  );
}

function Body({ d }: { d: Dashboard }) {
  const g = d.booking_trend.length > 0 && d.range ? (d.booking_trend.length > 62 ? "week" : "day") : "day";
  const bookingData = d.booking_trend.map((b) => ({ label: formatBucket(b.bucket, g), Bookings: b.total, Confirmed: b.confirmed }));
  const payData = d.revenue_trend.map((p) => ({ label: formatBucket(p.bucket, g), Captured: p.captured_paise }));
  const t = d.totals;
  const p = d.period;
  return (
    <div className="space-y-6">
      <section aria-label="Platform totals" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Active customers" value={formatNumber(t.active_customers)} hint={`${formatNumber(t.customers)} registered · ${formatNumber(t.suspended_customers)} suspended · ${formatNumber(p.new_customers)} new in period`} icon={Users} />
        <StatCard label="Active venue owners" value={formatNumber(t.active_owners)} hint={`${formatNumber(t.owners)} registered · ${formatNumber(t.suspended_owners)} suspended · ${formatNumber(p.new_owners)} new in period`} icon={Store} />
        <StatCard label="Pending venue approvals" value={formatNumber(t.pending_venue_approvals)} hint={t.pending_venue_approvals ? "Review them in Venues" : "Nothing waiting"} icon={BadgeCheck} tone={t.pending_venue_approvals ? "warning" : "primary"} />
        <StatCard label="Venues" value={formatNumber(t.venues)} hint={`${formatNumber(t.published_venues)} published · ${formatNumber(t.open_venue_reports)} open reports`} icon={MapPin} />
        <StatCard label="Payments" value={formatMoney(p.money.successful_payment_paise)} hint={`${formatNumber(p.transactions)} transactions in period`} icon={CreditCard} trend={payData.map((r) => r.Captured)} />
      </section>
      <section aria-label="Booking status in period" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Bookings created" value={formatNumber(p.bookings)} hint={`${formatNumber(t.bookings)} all time`} icon={CalendarCheck} trend={bookingData.map((r) => r.Bookings)} />
        <StatCard label="Confirmed (upcoming)" value={formatNumber(p.confirmed)} icon={CalendarCheck} tone="success" />
        <StatCard label="Completed" value={formatNumber(p.completed)} hint="Finished bookings, counted separately" icon={ShieldCheck} tone="success" />
        <StatCard label="Cancelled" value={formatNumber(p.cancelled)} icon={CalendarX2} tone="danger" />
        <StatCard label="Failed payments" value={formatNumber(p.failed_payments)} hint={`${formatNumber(p.pending)} bookings awaiting payment`} icon={p.failed_payments ? AlertTriangle : CalendarClock} tone={p.failed_payments ? "danger" : "warning"} />
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-start justify-between gap-3"><div className="flex flex-col gap-1"><CardTitle>Booking trend</CardTitle><CardDescription>Bookings created per {d.booking_trend.length > 62 ? "week" : "day"}</CardDescription></div><p className="text-xl font-semibold tracking-tight">{formatNumber(p.bookings)}</p></CardHeader>
          <CardContent><TrendChart title="Booking trend" data={bookingData} series={[{ key: "Bookings", label: "Bookings" }, { key: "Confirmed", label: "Confirmed", color: 3 }]} /></CardContent>
        </Card>
        <Card>
          <CardHeader className="flex-row items-start justify-between gap-3"><div className="flex flex-col gap-1"><CardTitle>Recorded payment trend</CardTitle><CardDescription>Captured payments, gross (not revenue)</CardDescription></div><p className="text-xl font-semibold tracking-tight">{formatMoney(p.money.successful_payment_paise)}</p></CardHeader>
          <CardContent><TrendChart title="Payment trend" data={payData} series={[{ key: "Captured", label: "Captured" }]} valueFormat="money" kind="bar" /></CardContent>
        </Card>
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2"><MoneyPanel money={p.money} /></div>
        <Card>
          <CardHeader className="flex-row items-start justify-between gap-3"><div className="flex flex-col gap-1"><CardTitle>Popular venues</CardTitle><CardDescription>Most booked in this period</CardDescription></div><Link href="/venues" className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">View all <ArrowRight className="size-4" aria-hidden /></Link></CardHeader>
          <CardContent>
            {d.popular_venues.length === 0 ? <EmptyState title="No bookings in this period" /> : (
              <ol className="space-y-3">
                {d.popular_venues.map((v, i) => (
                  <li key={v.venue_id} className="flex items-center gap-3">
                    <span className="flex size-7 items-center justify-center rounded-full bg-primary-tint text-xs font-semibold text-primary">{i + 1}</span>
                    <Link href={`/venues/${v.venue_id}`} className="min-w-0 flex-1 truncate font-medium hover:underline">{v.name}</Link>
                    <span className="text-sm text-muted-foreground">{v.bookings}</span>
                  </li>
                ))}
              </ol>
            )}
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader className="flex-row items-center justify-between"><CardTitle>Recent bookings</CardTitle><Link href="/bookings" className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">View all <ArrowRight className="size-4" aria-hidden /></Link></CardHeader>
        <CardContent className="p-0">
          {d.recent_bookings.length === 0 ? <EmptyState title="No bookings yet" description="Bookings appear here as customers book venues." /> : <BriefBookings items={d.recent_bookings} />}
        </CardContent>
      </Card>

      <section className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Recent registrations</CardTitle></CardHeader>
          <CardContent>
            {d.recent_registrations.length === 0 ? <EmptyState title="No registrations yet" /> : (
              <ul className="divide-y divide-border">
                {d.recent_registrations.map((r) => (
                  <li key={r.id} className="flex items-center justify-between gap-3 py-3">
                    <Link href={`/${r.role === "owner" ? "owners" : "customers"}/${r.id}`} className="font-medium hover:underline">{r.full_name}</Link>
                    <span className="flex items-center gap-3"><Badge tone={r.role === "owner" ? "primary" : "neutral"}>{titleCase(r.role)}</Badge><span className="text-xs text-muted-foreground">{formatDateTime(r.created_at)}</span></span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Platform activity</CardTitle><CardDescription>Latest bookings, payments and account events</CardDescription></CardHeader>
          <CardContent>
            {d.activity.length === 0 ? <EmptyState title="No activity yet" /> : (
              <ul className="divide-y divide-border">
                {d.activity.map((a, i) => (
                  <li key={`${a.created_at}-${i}`} className="flex items-start justify-between gap-3 py-3">
                    <div className="min-w-0"><p className="text-sm font-medium">{a.title}</p>{a.detail && <p className="truncate text-xs text-muted-foreground">{a.detail}</p>}</div>
                    <span className="shrink-0 text-xs text-muted-foreground">{formatDateTime(a.created_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </section>
      <p className="text-xs text-muted-foreground"><Wallet className="mr-1 inline size-3.5" aria-hidden />All amounts are in {p.money.currency}. {formatMoney(0)} means nothing was recorded, not that data is missing.</p>
    </div>
  );
}
