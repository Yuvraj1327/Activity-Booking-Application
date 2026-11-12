/** Display helpers. Money arrives as integer paise; nothing here changes a value. */

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
const num = new Intl.NumberFormat("en-IN");

export function formatMoney(paise: number | null | undefined, currency = "INR"): string {
  if (paise === null || paise === undefined) return "—";
  if (currency !== "INR") return `${(paise / 100).toFixed(2)} ${currency}`;
  return inr.format(paise / 100);
}

export function formatNumber(n: number | null | undefined): string {
  return n === null || n === undefined ? "—" : num.format(n);
}

const REPORT_TZ = process.env.NEXT_PUBLIC_ADMIN_REPORT_TIMEZONE || "Asia/Kolkata";

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: REPORT_TZ }).format(new Date(iso));
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  // Plain dates (YYYY-MM-DD) are shown as-is, without time-zone shifting.
  const d = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? new Date(`${iso}T00:00:00Z`) : new Date(iso);
  return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeZone: /^\d{4}-\d{2}-\d{2}$/.test(iso) ? "UTC" : REPORT_TZ }).format(d);
}

export function formatBucket(iso: string, granularity: "day" | "week" | "month"): string {
  const d = new Date(`${iso}T00:00:00Z`);
  const opts: Intl.DateTimeFormatOptions =
    granularity === "month" ? { month: "short", year: "2-digit" } : { day: "numeric", month: "short" };
  return new Intl.DateTimeFormat("en-IN", { ...opts, timeZone: "UTC" }).format(d);
}

export function duration(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h} h ${m} min` : `${h} h`;
}

export function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export type Tone = "neutral" | "success" | "warning" | "danger" | "info" | "primary";

const TONES: Record<string, Tone> = {
  active: "success", published: "success", confirmed: "success", completed: "success", captured: "success", paid: "success",
  pending_payment: "warning", pending: "warning", created: "warning", authorized: "info", unpaid: "neutral", draft: "neutral",
  suspended: "danger", failed: "danger", payment_failed: "danger", cancelled_by_customer: "danger", cancelled_by_owner: "danger",
  expired: "neutral", archived: "neutral", refunded: "info", partially_refunded: "info", refund_pending: "warning",
};
export const toneOf = (status: string): Tone => TONES[status] ?? "neutral";

export const BOOKING_STATUSES = [
  "pending_payment", "payment_failed", "confirmed", "expired", "cancelled_by_customer", "cancelled_by_owner",
  "completed", "refund_pending", "refunded",
];
export const BOOKING_PAYMENT_STATUSES = ["unpaid", "pending", "paid", "failed", "refunded", "partially_refunded"];
export const PAYMENT_STATUSES = ["created", "pending", "authorized", "captured", "failed", "refunded", "partially_refunded"];
