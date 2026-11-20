import Image from "next/image";

/**
 * Frame for sign-in, two-step verification and "not authorised". The designed background (admin
 * console pitch on the left, court artwork on the right) shows from desktop width, filling the
 * screen on wide windows and fitting whole (never cropping its text) on squarer ones. Smaller
 * screens, and the dark theme (the picture's headline is dark text), get a plain brand gradient.
 */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="relative isolate flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-br from-primary-tint via-background to-background p-6">
      <Image
        src="/auth-bg.webp"
        alt=""
        fill
        priority
        sizes="100vw"
        className="-z-20 hidden scale-105 object-cover object-center opacity-90 blur-[2px] lg:block dark:lg:hidden [@media(max-aspect-ratio:17/10)]:object-contain"
      />
      {/* Soft wash over the artwork so it reads as a background and the card stands out. */}
      <div aria-hidden className="absolute inset-0 -z-10 hidden bg-gradient-to-b from-white/20 via-white/5 to-white/25 lg:block dark:lg:hidden" />
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-8 shadow-2xl shadow-primary/15 ring-1 ring-primary/10">
        <Image src="/logo.png" alt="ZURUV Admin" width={800} height={168} priority className="mb-6 h-auto w-48 dark:hidden" />
        <Image src="/logo-dark.png" alt="ZURUV Admin" width={800} height={168} priority className="mb-6 hidden h-auto w-48 dark:block" />
        {children}
      </div>
    </main>
  );
}
