import Image from "next/image";
import { Suspense, use } from "react";
import Link from "next/link";
import { Bell, ChevronDown } from "lucide-react";
import { HeaderSearch } from "@/components/layout/header-search";
import { MobileMenu } from "@/components/layout/mobile-menu";
import { SignOutButton } from "@/components/layout/sign-out-button";

export function Header({ adminName, unread, permissions, roleName }: { adminName: string; unread: Promise<number>; permissions: string[]; roleName: string | null }) {
  const initials = adminName.split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  return (
    <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center justify-between gap-2 border-b border-border bg-card/95 px-3 sm:gap-4 sm:px-4 backdrop-blur md:px-6">
      <MobileMenu adminName={adminName} permissions={permissions} />
      <Link href="/dashboard" aria-label="ZURUV Admin home" className="flex shrink-0 items-center md:hidden">
        <Image src="/logo.png" alt="ZURUV" width={800} height={168} priority className="h-8 w-auto dark:hidden" />
        <Image src="/logo-dark.png" alt="ZURUV" width={800} height={168} priority className="hidden h-8 w-auto dark:block" />
      </Link>
      <h1 className="hidden shrink-0 text-lg font-semibold tracking-tight md:block">Admin Console</h1>
      <div className="flex min-w-0 flex-1 justify-center"><HeaderSearch /></div>
      <span className="flex-1 md:hidden" aria-hidden />
      <div className="flex shrink-0 items-center gap-2 md:gap-4">
        <Suspense fallback={<Bell0 />}><BellLink unread={unread} /></Suspense>
        <Link href="/settings#profile" aria-label="Your profile and settings" className="flex items-center gap-2 rounded-xl px-1.5 py-1 hover:bg-muted">
          <span aria-hidden className="flex size-9 items-center justify-center rounded-full bg-primary-tint text-xs font-semibold text-primary">{initials || "A"}</span>
          <div className="hidden leading-tight sm:block">
            <p className="text-sm font-medium" data-testid="admin-name">{adminName}</p>
            <p className="text-xs text-muted-foreground" data-testid="admin-role">{roleName ?? "No role assigned"}</p>
          </div>
          <ChevronDown className="hidden size-4 text-muted-foreground sm:block" aria-hidden />
        </Link>
        <div className="hidden md:block"><SignOutButton /></div>
      </div>
    </header>
  );
}

function Bell0() {
  return (
    <Link href="/notifications" aria-label="Notifications" className="relative inline-flex size-10 items-center justify-center rounded-full hover:bg-muted" data-testid="bell">
      <Bell className="size-5" aria-hidden />
    </Link>
  );
}

function BellLink({ unread: pending }: { unread: Promise<number> }) {
  const unread = use(pending);
  return (
    <Link href="/notifications" aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
    className="relative inline-flex size-10 items-center justify-center rounded-full hover:bg-muted" data-testid="bell">
    <Bell className="size-5" aria-hidden />
    {unread > 0 && (
      <span className="absolute right-1 top-1 flex min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold leading-4 text-white" data-testid="bell-count">
        {unread > 99 ? "99+" : unread}
      </span>
    )}
  </Link>
  );
}
