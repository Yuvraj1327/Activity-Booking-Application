"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { navGroups } from "@/lib/nav";

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="sticky top-0 hidden h-screen shrink-0 flex-col border-r border-border bg-card md:flex md:w-[4.5rem] lg:w-64">
      <div className="flex h-16 items-center gap-2 px-4 lg:px-6">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary text-sm font-bold text-primary-foreground">Z</span>
        <span className="hidden text-lg font-bold tracking-tight text-primary lg:inline">ZURUV</span>
        <span className="ml-auto hidden rounded-full bg-primary-tint px-2 py-0.5 text-[10px] font-semibold uppercase text-primary lg:inline">Admin</span>
      </div>
      <nav aria-label="Main" className="flex flex-1 flex-col gap-4 overflow-y-auto px-3 py-2">
        {navGroups.map((g) => (
          <div key={g.title} className="flex flex-col gap-1">
            <p className="hidden px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground lg:block">{g.title}</p>
            {g.items.map(({ label, href, icon: Icon }) => {
              const active = pathname === href || pathname.startsWith(`${href}/`);
              return (
                <Link
                  key={href}
                  href={href}
                  title={label}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center justify-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium lg:justify-start",
                    active ? "bg-primary-tint text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground",
                  )}
                >
                  <Icon className="size-[18px] shrink-0" aria-hidden />
                  <span className="hidden lg:inline">{label}</span>
                  <span className="sr-only lg:hidden">{label}</span>
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
    </aside>
  );
}

/** Below tablet width: a horizontally scrolling tab strip instead of the rail. */
export function MobileNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main (compact)" className="flex gap-1 overflow-x-auto border-b border-border bg-card px-3 py-2 md:hidden">
      {navGroups.flatMap((g) => g.items).map(({ label, href }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link key={href} href={href} aria-current={active ? "page" : undefined}
            className={cn("shrink-0 rounded-md px-3 py-1.5 text-sm", active ? "bg-primary-tint font-medium text-primary" : "text-muted-foreground")}>
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
