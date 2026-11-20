import Image from "next/image";
import Link from "next/link";
import { BarChart3, CalendarCheck, Store, Trophy } from "lucide-react";

const ACTIONS = [
  { href: "/bookings", label: "Manage Bookings", icon: CalendarCheck },
  { href: "/venues", label: "Add & Verify Venues", icon: Store },
  { href: "/payments", label: "Track Revenue", icon: BarChart3 },
] as const;

// Where the three button pills sit inside the banner image (2000x667 reference), as percentages,
// so the clickable areas stay aligned at any width.
const HOTSPOTS = [
  { ...ACTIONS[0], left: 4.1, top: 67.8, width: 12.75, height: 9.7 },
  { ...ACTIONS[1], left: 17.95, top: 67.8, width: 13.95, height: 9.7 },
  { ...ACTIONS[2], left: 33, top: 67.8, width: 12.55, height: 9.7 },
] as const;

/** Welcome banner. Tablet/desktop: the designed banner image with clickable buttons on top. Phones: live text. */
export function DashboardHero() {
  return (
    <>
      <section aria-label="Welcome" className="relative hidden overflow-hidden rounded-2xl border border-border shadow-sm md:block">
        <Image
          src="/dashboard-banner-3.webp"
          alt="Welcome to ZURUV. Manage venues, bookings and sports in one place. A complete platform to run and grow your sports marketplace."
          width={2000}
          height={667}
          priority
          sizes="(min-width: 1024px) calc(100vw - 20rem), 100vw"
          className="block h-auto w-full dark:brightness-90"
        />
        {HOTSPOTS.map(({ href, label, left, top, width, height }) => (
          <Link
            key={href}
            href={href}
            aria-label={label}
            className="absolute rounded-xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            style={{ left: `${left}%`, top: `${top}%`, width: `${width}%`, height: `${height}%` }}
          />
        ))}
      </section>
      <LiveHero />
    </>
  );
}

/** Text version used below tablet width, where the banner image would be too small to read. */
function LiveHero() {
  return (
    <section
      aria-label="Welcome"
      className="relative isolate overflow-hidden rounded-2xl border border-border bg-gradient-to-br from-primary-tint via-card to-card md:hidden"
    >
      <Trophy className="pointer-events-none absolute -right-6 -top-6 -z-10 size-40 rotate-12 text-primary/10" aria-hidden />
      <div className="relative px-4 py-6 sm:px-6 sm:py-8">
        <Image src="/logo.png" alt="ZURUV" width={800} height={168} className="h-9 w-auto dark:hidden" />
        <Image src="/logo-dark.png" alt="ZURUV" width={800} height={168} className="hidden h-9 w-auto dark:block" />
        <span className="mt-5 inline-flex rounded-full bg-primary-tint px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-primary">
          Welcome to ZURUV
        </span>
        <h2 className="mt-3 text-2xl font-bold leading-tight tracking-tight sm:text-3xl">
          Manage Venues, Bookings &amp; Sports in <span className="text-primary">One Place</span>
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">A complete platform to run and grow your sports marketplace.</p>
        <div className="mt-5 grid grid-cols-1 gap-2.5 min-[420px]:grid-cols-3">
          {ACTIONS.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className="flex items-center gap-2.5 rounded-xl border border-border bg-card/80 px-3 py-2.5 text-sm font-medium shadow-sm backdrop-blur transition-colors hover:bg-card focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary min-[420px]:flex-col min-[420px]:gap-1.5 min-[420px]:py-3 min-[420px]:text-center min-[420px]:text-xs"
            >
              <Icon className="size-5 shrink-0 text-primary" aria-hidden />
              {label}
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
