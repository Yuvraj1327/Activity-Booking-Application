/** Commission management API shapes (the backend does every calculation; the UI only displays). */

export type CommissionVersion = {
  id: string;
  rule_id: string;
  version: number;
  commission_bps: number;
  commission_pct: string | null;
  previous_bps: number | null;
  previous_pct: string | null;
  is_active: boolean;
  effective_from: string;
  effective_to: string | null;
  reason: string;
  changed_by: string | null;
  changed_by_name: string | null;
  created_at: string;
};

export type CommissionRule = {
  id: string;
  scope: "global" | "activity" | "venue";
  category_id: string | null;
  category_name: string | null;
  venue_id: string | null;
  venue_name: string | null;
  created_at: string;
  current: CommissionVersion | null;
  is_active_now: boolean;
  pending: CommissionVersion[];
  latest_version: number;
};

export type RulesResponse = {
  priority: string[];
  priority_note: string;
  activity_tiebreak: string | null;
  ambiguous_venues: { venue_id: string; venue_name: string; percentages: number[] }[];
  global: CommissionRule | null;
  items: CommissionRule[];
};

export type HistoryRow = Omit<CommissionVersion, "id"> & { id: string; scope: string; category_name: string | null; venue_name: string | null; venue_id: string | null; category_id: string | null };

export type Totals = { sales_gross_paise: number; refunded_gross_paise: number; net_gross_paise: number; commission_accrued_paise: number; commission_reversed_paise: number; net_commission_paise: number; owner_net_paise: number; platform_net_paise: number; tax_paise: number; bookings: number };
export type Check = { key: string; label: string; mismatches: number; ok: boolean; informational?: boolean };
export type CommissionReport = {
  range: { date_from: string; date_to: string };
  totals: Totals;
  by_activity: (Totals & { category_id: string | null; category_name: string })[];
  by_venue: (Totals & { venue_id: string; venue_name: string })[];
  by_day: (Totals & { date: string })[];
  by_scope: (Totals & { scope: string })[];
  reconciliation: { ok: boolean; checks: Check[] };
};

export type BookingCommission = {
  booking_id: string;
  snapshot: { scope: string; rule_id: string | null; rule_version: number | null; commission_bps: number | null; commission_pct: string | null; category_name: string | null; effective_at: string; source: string; candidates: { scope: string; commission_bps: number; version: number; selected: boolean; is_active: boolean }[] } | null;
  calculation: { gross_paise: number; commission_base_paise: number | null; commission_bps: number | null; commission_pct: string | null; commission_scope: string | null; commission_rule_version: number | null; commission_paise: number; owner_net_paise: number; finance_config_version: number; occurred_at: string } | null;
  net: { gross_paise: number; commission_paise: number; owner_net_paise: number; platform_paise: number; refunded_paise: number };
  note: string | null;
};

export const SCOPE_LABEL: Record<string, string> = { venue: "Venue-specific", activity: "Activity-specific", global: "Global default", finance_config: "Finance configuration (fallback)", none: "No rule", legacy: "Before commission rules" };
export const bpsHelp = "Basis points: 1000 = 10%, 1250 = 12.5%. Allowed 0 to 10000.";
