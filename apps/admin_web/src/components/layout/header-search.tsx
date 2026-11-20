"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

const SCOPES = [
  { value: "venues", label: "Venues" },
  { value: "customers", label: "Customers" },
  { value: "owners", label: "Owners" },
] as const;

/** Jumps to a list page with its existing `q` filter applied (the API searches each list server-side). */
export function HeaderSearch() {
  const router = useRouter();
  const [scope, setScope] = useState<(typeof SCOPES)[number]["value"]>("venues");
  const [q, setQ] = useState("");

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const text = q.trim();
    if (!text) return;
    router.push(`/${scope}?q=${encodeURIComponent(text)}`);
  }

  return (
    <form onSubmit={onSubmit} role="search" className="hidden h-11 w-full max-w-xl items-center gap-2 rounded-xl border border-border bg-background px-3 shadow-sm focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/30 md:flex">
      <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        maxLength={100}
        placeholder={`Search ${scope}...`}
        aria-label={`Search ${scope}`}
        className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
      />
      <select
        value={scope}
        onChange={(e) => setScope(e.target.value as typeof scope)}
        aria-label="Search in"
        className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground outline-none"
      >
        {SCOPES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
      </select>
    </form>
  );
}
