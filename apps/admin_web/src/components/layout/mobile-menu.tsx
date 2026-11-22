"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";
import { useEffect, useState } from "react";
import { SignOutButton } from "@/components/layout/sign-out-button";
import { settingsItem, visibleGroups } from "@/lib/nav";
import { cn } from "@/lib/utils";

/** Phone-only hamburger that opens a slide-in sidebar with every navigation entry. */
export function MobileMenu({ adminName, permissions }: { adminName: string; permissions: string[] }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open]);

  const linkCls = (active: boolean) =>
    cn(
      "flex items-center gap-3 rounded-lg px-3 py-3 text-sm font-medium",
      active ? "bg-primary-tint text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground",
    );
  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  return (
    <div className="md:hidden">
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open menu"
        aria-expanded={open}
        className="inline-flex size-10 items-center justify-center rounded-full hover:bg-muted"
      >
        <Menu className="size-5" aria-hidden />
      </button>

      <div className={cn("fixed inset-0 z-40 transition-opacity", open ? "opacity-100" : "pointer-events-none opacity-0")} aria-hidden={!open}>
        <div className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} />
        <aside
          role="dialog"
          aria-modal="true"
          aria-label="Menu"
          className={cn(
            "absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col bg-card shadow-xl transition-transform duration-200",
            open ? "translate-x-0" : "-translate-x-full",
          )}
        >
          <div className="flex h-16 shrink-0 items-center justify-between border-b border-border px-4">
            <Image src="/logo.png" alt="ZURUV" width={800} height={168} className="h-8 w-auto dark:hidden" />
            <Image src="/logo-dark.png" alt="ZURUV" width={800} height={168} className="hidden h-8 w-auto dark:block" />
            <button type="button" onClick={() => setOpen(false)} aria-label="Close menu" className="inline-flex size-10 items-center justify-center rounded-full hover:bg-muted">
              <X className="size-5" aria-hidden />
            </button>
          </div>
          <nav aria-label="Main (mobile)" onClick={(e) => (e.target as HTMLElement).closest("a") && setOpen(false)} className="flex flex-1 flex-col gap-4 overflow-y-auto px-3 py-3">
            {visibleGroups(permissions).map((g) => (
              <div key={g.title} className="flex flex-col gap-1">
                <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{g.title}</p>
                {g.items.map(({ label, href, icon: Icon }) => (
                  <Link key={href} href={href} aria-current={isActive(href) ? "page" : undefined} className={linkCls(isActive(href))}>
                    <Icon className="size-[18px] shrink-0" aria-hidden />
                    {label}
                  </Link>
                ))}
              </div>
            ))}
            <div className="flex flex-col gap-1 border-t border-border pt-3">
              <Link href={settingsItem.href} aria-current={isActive(settingsItem.href) ? "page" : undefined} className={linkCls(isActive(settingsItem.href))}>
                <settingsItem.icon className="size-[18px] shrink-0" aria-hidden />
                {settingsItem.label}
              </Link>
            </div>
          </nav>
          <div className="flex shrink-0 items-center justify-between gap-2 border-t border-border p-3">
            <div className="min-w-0 leading-tight">
              <p className="truncate text-sm font-medium">{adminName}</p>
              <p className="text-xs text-muted-foreground">Administrator</p>
            </div>
            <SignOutButton variant="outline" />
          </div>
        </aside>
      </div>
    </div>
  );
}
