import Link from "next/link";
import { Bell, ChevronDown } from "lucide-react";
import { HeaderSearch } from "@/components/layout/header-search";
import { SignOutButton } from "@/components/layout/sign-out-button";

export function Header({ adminName, unread }: { adminName: string; unread: number }) {
  const initials = adminName.split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  return (
    <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center justify-between gap-4 border-b border-border bg-card/95 px-4 backdrop-blur md:px-6">
      <span className="text-sm font-semibold text-primary md:hidden">ZURUV Admin</span>
      <h1 className="hidden shrink-0 text-lg font-semibold tracking-tight md:block">Admin Console</h1>
      <div className="flex min-w-0 flex-1 justify-center"><HeaderSearch /></div>
      <div className="flex shrink-0 items-center gap-2 md:gap-4">
        <Link href="/notifications" aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
          className="relative inline-flex size-10 items-center justify-center rounded-full hover:bg-muted" data-testid="bell">
          <Bell className="size-5" aria-hidden />
          {unread > 0 && (
            <span className="absolute right-1 top-1 flex min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold leading-4 text-white" data-testid="bell-count">
              {unread > 99 ? "99+" : unread}
            </span>
          )}
        </Link>
        <Link href="/settings#profile" aria-label="Your profile and settings" className="flex items-center gap-2 rounded-xl px-1.5 py-1 hover:bg-muted">
          <span aria-hidden className="flex size-9 items-center justify-center rounded-full bg-primary-tint text-xs font-semibold text-primary">{initials || "A"}</span>
          <div className="hidden leading-tight sm:block">
            <p className="text-sm font-medium" data-testid="admin-name">{adminName}</p>
            <p className="text-xs text-muted-foreground">Administrator</p>
          </div>
          <ChevronDown className="hidden size-4 text-muted-foreground sm:block" aria-hidden />
        </Link>
        <SignOutButton />
      </div>
    </header>
  );
}
