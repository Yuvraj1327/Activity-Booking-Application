/** URL-state helpers: filters, paging and date ranges live in the query string (shareable, no client state). */

export type SearchParams = Record<string, string | string[] | undefined>;

export function one(params: SearchParams, key: string): string | undefined {
  const v = params[key];
  const s = Array.isArray(v) ? v[0] : v;
  return s && s.trim() ? s.trim() : undefined;
}

export const PAGE_SIZE = 20;

export function pageOf(params: SearchParams): { offset: number; page: number } {
  const raw = Number(one(params, "page") ?? "1");
  const page = Number.isInteger(raw) && raw >= 1 && raw <= 5000 ? raw : 1;
  return { offset: (page - 1) * PAGE_SIZE, page };
}

/** Build "/path?a=1&b=2", dropping empty values. `overrides` replace values (undefined removes). */
export function href(path: string, params: SearchParams, overrides: Record<string, string | undefined> = {}): string {
  const merged: Record<string, string | undefined> = {};
  for (const [k, v] of Object.entries(params)) merged[k] = Array.isArray(v) ? v[0] : v;
  Object.assign(merged, overrides);
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(merged)) if (v !== undefined && v !== "") qs.set(k, v);
  const s = qs.toString();
  return s ? `${path}?${s}` : path;
}

export const REPORT_TZ = process.env.ADMIN_REPORT_TIMEZONE || process.env.NEXT_PUBLIC_ADMIN_REPORT_TIMEZONE || "Asia/Kolkata";

/** Calendar date (YYYY-MM-DD) in the reporting time zone. */
export function todayIn(tz: string = REPORT_TZ, now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
  return parts; // en-CA yields YYYY-MM-DD
}

function addDays(day: string, n: number): string {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export const PRESETS = [
  { key: "today", label: "Today" },
  { key: "7d", label: "Last 7 days" },
  { key: "30d", label: "Last 30 days" },
  { key: "month", label: "This month" },
] as const;
export type PresetKey = (typeof PRESETS)[number]["key"] | "custom";

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

export type Range = { from: string; to: string; preset: PresetKey };

/** Resolve ?range=today|7d|30d|month or ?from=&to= into concrete dates. Default: last 30 days. */
export function resolveRange(params: SearchParams, now: Date = new Date(), tz: string = REPORT_TZ): Range {
  const today = todayIn(tz, now);
  const from = one(params, "from");
  const to = one(params, "to");
  if (from && to && ISO_DAY.test(from) && ISO_DAY.test(to) && from <= to) return { from, to, preset: "custom" };
  switch (one(params, "range")) {
    case "today":
      return { from: today, to: today, preset: "today" };
    case "7d":
      return { from: addDays(today, -6), to: today, preset: "7d" };
    case "month":
      return { from: `${today.slice(0, 7)}-01`, to: today, preset: "month" };
    default:
      return { from: addDays(today, -29), to: today, preset: "30d" };
  }
}
