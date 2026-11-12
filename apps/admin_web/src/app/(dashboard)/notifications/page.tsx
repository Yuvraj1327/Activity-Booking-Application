import type { Metadata } from "next";
import Link from "next/link";
import { Bell, CheckCheck } from "lucide-react";
import { markAllNotificationsRead, markNotificationRead } from "@/app/actions";
import { FilterBar } from "@/components/data/filter-bar";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDateTime } from "@/lib/format";
import { one, PAGE_SIZE, pageOf, type SearchParams } from "@/lib/query";
import type { AppNotification, Paged } from "@/lib/types";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Notifications" };

function target(n: AppNotification): string | null {
  if (n.type === "payment.review" && n.payment_id) return `/payments/${n.payment_id}`;
  if (n.payment_id) return `/payments/${n.payment_id}`;
  if (n.booking_id) return `/bookings/${n.booking_id}`;
  if (n.type === "admin.new_owner") return "/owners";
  if (n.type === "admin.new_customer") return "/customers";
  return null;
}

export default async function NotificationsPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const { offset, page } = pageOf(params);
  const unreadOnly = one(params, "show") === "unread";
  const res = await safe(adminGet<Paged<AppNotification>>("/notifications", { unread_only: unreadOnly || undefined, limit: PAGE_SIZE, offset }));
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="Notifications" description="New registrations, important payment events and account status changes."
        actions={<form action={markAllNotificationsRead}><Button variant="outline" size="sm" type="submit" data-testid="mark-all"><CheckCheck className="size-4" aria-hidden /> Mark all read</Button></form>} />
      <Card>
        <FilterBar path="/notifications" params={params} fields={[{ kind: "select", name: "show", label: "Show", options: [{ value: "unread", label: "Unread only" }] }]} />
        {!res.ok ? <div className="p-4"><ErrorState message={`Could not load notifications (${res.error.message}).`} /></div> : res.data.items.length === 0 ? (
          <EmptyState title={unreadOnly ? "You are all caught up" : "No notifications yet"} description="Platform events will appear here." />
        ) : (
          <>
            <ul className="divide-y divide-border">
              {res.data.items.map((n) => {
                const to = target(n);
                return (
                  <li key={n.id} data-testid="notification" data-read={n.is_read} className={cn("flex items-start gap-3 p-4", !n.is_read && "bg-primary-tint/50")}>
                    <span className={cn("mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-full", n.is_read ? "bg-muted text-muted-foreground" : "bg-primary text-primary-foreground")}><Bell className="size-4" aria-hidden /></span>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">{n.title} {!n.is_read && <Badge tone="primary">New</Badge>}</p>
                      {n.body && <p className="mt-0.5 text-sm text-muted-foreground">{n.body}</p>}
                      <p className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">{formatDateTime(n.created_at)}{to && <Link href={to} className="text-primary hover:underline">View</Link>}</p>
                    </div>
                    {!n.is_read && (
                      <form action={markNotificationRead}><input type="hidden" name="id" value={n.id} /><Button type="submit" variant="ghost" size="sm">Mark read</Button></form>
                    )}
                  </li>
                );
              })}
            </ul>
            <Pagination path="/notifications" params={params} page={page} hasMore={res.data.has_more} shown={res.data.items.length} />
          </>
        )}
      </Card>
    </div>
  );
}
