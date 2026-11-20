import Image from "next/image";
import Link from "next/link";
import { BarChart3, CalendarCheck, Store } from "lucide-react";

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
      <div className="relative max-w-xl px-6 py-8 md:px-8 md:py-10 lg:max-w-[52%]">
        <span className="inline-flex rounded-full bg-primary-tint px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-primary">
          Welcome to ZURUV
        </span>
        <h2 className="mt-4 text-3xl font-bold leading-tight tracking-tight lg:text-4xl">
          Manage Venues, Bookings &amp; Sports in <span className="text-primary">One Place</span>
        </h2>
        <p className="mt-3 text-sm text-muted-foreground md:text-base">A complete platform to run and grow your sports marketplace.</p>
        <div className="mt-6 flex flex-wrap gap-2.5">
          {ACTIONS.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className="inline-flex items-center gap-2 rounded-xl border border-border bg-card/80 px-3.5 py-2.5 text-sm font-medium shadow-sm backdrop-blur transition-colors hover:bg-card focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            >
              <Icon className="size-[18px] text-primary" aria-hidden />
              {label}
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
