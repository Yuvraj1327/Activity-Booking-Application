import Link from "next/link";
import { Bell } from "lucide-react";
import { SignOutButton } from "@/components/layout/sign-out-button";

export function Header({ adminName, unread }: { adminName: string; unread: number }) {
  const initials = adminName.split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  return (
    <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center justify-between border-b border-border bg-card/95 px-4 backdrop-blur md:px-6">
      <span className="text-sm font-semibold text-primary md:hidden">ZURUV Admin</span>
      <h1 className="hidden text-sm font-medium text-muted-foreground md:block">Admin console</h1>
      <div className="flex items-center gap-2 md:gap-4">
        <Link href="/notifications" aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
          className="relative inline-flex size-10 items-center justify-center rounded-full hover:bg-muted" data-testid="bell">
          <Bell className="size-5" aria-hidden />
          {unread > 0 && (
            <span className="absolute right-1 top-1 flex min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold leading-4 text-white" data-testid="bell-count">
              {unread > 99 ? "99+" : unread}
            </span>
          )}
        </Link>
        <div className="flex items-center gap-2">
          <span aria-hidden className="flex size-9 items-center justify-center rounded-full bg-primary-tint text-xs font-semibold text-primary">{initials || "A"}</span>
          <div className="hidden leading-tight sm:block">
            <p className="text-sm font-medium" data-testid="admin-name">{adminName}</p>
            <p className="text-xs text-muted-foreground">Administrator</p>
          </div>
        </div>
        <SignOutButton />
      </div>
    </header>
  );
}
