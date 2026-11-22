import { formatMoney } from "@/lib/format";

export type Coupon = {
  id: string; code: string; description: string | null; discount_type: "percent" | "fixed"; percent_bps: number | null; fixed_paise: number | null;
  max_discount_paise: number | null; min_booking_paise: number; valid_from: string | null; valid_until: string | null; usage_limit_total: number | null;
  usage_limit_per_user: number | null; first_booking_only: boolean; eligible_category_ids: string[]; eligible_city_ids: string[]; eligible_venue_ids: string[]; is_active: boolean; redeemed: number | null;
};

export function describe(c: Coupon): string {
  return c.discount_type === "percent" ? `${(c.percent_bps ?? 0) / 100}% off${c.max_discount_paise ? ` (max ${formatMoney(c.max_discount_paise)})` : ""}` : `${formatMoney(c.fixed_paise)} off`;
}

