"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { ArrowRight, Trophy } from "lucide-react";
import { navGroups, settingsItem } from "@/lib/nav";

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="sticky top-0 hidden h-screen shrink-0 flex-col border-r border-border bg-card md:flex md:w-[4.5rem] lg:w-72">
      <div className="flex h-16 items-center gap-2 px-4 lg:px-6">
        <Image src="/logo-mark.png" alt="ZURUV" width={36} height={36} className="size-9 shrink-0 rounded-md bg-white lg:hidden" />
        <Image src="/logo.png" alt="ZURUV" width={800} height={168} className="hidden h-9 w-auto lg:block dark:lg:hidden" />
        <Image src="/logo-dark.png" alt="ZURUV" width={800} height={168} className="hidden h-9 w-auto dark:lg:block" />
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
      <div className="hidden px-3 pb-3 lg:[@media(min-height:880px)]:block">
        <Link
          href="/venues"
          className="relative block overflow-hidden rounded-2xl bg-gradient-to-br from-primary-tint to-card p-4 ring-1 ring-border transition-shadow hover:shadow-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          <Trophy className="absolute -right-2 -top-2 size-16 rotate-12 text-primary/15" aria-hidden />
          <p className="relative text-base font-semibold leading-snug">Grow your sports marketplace</p>
          <p className="relative mt-1.5 text-xs text-muted-foreground">Add venues, manage bookings and increase activity.</p>
          <span className="relative mt-3 flex size-9 items-center justify-center rounded-full bg-primary text-primary-foreground ml-auto">
            <ArrowRight className="size-4" aria-hidden />
            <span className="sr-only">Go to venues</span>
          </span>
        </Link>
      </div>
      <div className="border-t border-border px-3 py-3">
        {(() => {
          const { label, href, icon: Icon } = settingsItem;
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
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
        })()}
      </div>
    </aside>
  );
}
