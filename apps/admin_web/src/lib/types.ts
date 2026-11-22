// Mirrors backend/app/schemas/admin.py (and the payment/booking schemas). Money is integer paise.

export type Unavailable = { available: false; depends_on: string; message: string };

export type Paged<T> = { items: T[]; limit: number; offset: number; has_more: boolean };

export type DateRange = { date_from: string; date_to: string; timezone: string };

export type Figure = { available: true; amount_paise: number; note: string };
export type Money = {
  currency: string;
  gross_booking_value_paise: number;
  successful_payment_paise: number;
  platform_revenue: Figure | Unavailable;
  owner_earnings: Figure | Unavailable;
  refunds: Figure | Unavailable;
  tax_collected?: Figure | Unavailable | null;
  ledger_coverage?: { captured_payments: number; with_ledger_entry: number; without_ledger_entry: number } | null;
};

export type BookingBucket = {
  bucket: string;
  total: number;
  confirmed: number;
  completed: number;
  pending: number;
  cancelled: number;
  other: number;
};
export type PaymentBucket = {
  bucket: string;
  captured_count: number;
  captured_paise: number;
  failed_count: number;
  open_count: number;
};
export type TopVenue = { venue_id: string; name: string; bookings: number; confirmed: number; completed: number };

export type BookingBrief = {
  id: string;
  booking_code: string;
  venue_name: string;
  customer_name: string;
  booking_date: string;
  status: string;
  payment_status: string;
  total_amount_paise: number;
  currency: string;
  created_at: string;
};

export type Activity = { kind: string; title: string; detail: string | null; created_at: string; entity_id: string | null };

export type Dashboard = {
  range: DateRange;
  totals: {
    customers: number; owners: number; venues: number; published_venues: number; bookings: number; payments: number;
    active_customers: number; active_owners: number; suspended_customers: number; suspended_owners: number;
    pending_venue_approvals: number; open_venue_reports: number;
  };
  period: {
    bookings: number;
    confirmed: number;
    completed: number;
    pending: number;
    cancelled: number;
    transactions: number;
    failed_payments: number;
    money: Money;
    new_customers: number;
    new_owners: number;
  };
  booking_trend: BookingBucket[];
  revenue_trend: PaymentBucket[];
  recent_bookings: BookingBrief[];
  recent_registrations: { id: string; full_name: string; role: string; created_at: string }[];
  popular_venues: TopVenue[];
  activity: Activity[];
};

export type Granularity = "day" | "week" | "month";

export type BookingAnalytics = {
  range: DateRange;
  granularity: Granularity;
  total: number;
  series: BookingBucket[];
  status_distribution: { status: string; count: number }[];
};
export type RevenueAnalytics = {
  range: DateRange;
  granularity: Granularity;
  transactions_total: number;
  captured_count: number;
  failed_count: number;
  open_count: number;
  success_rate_percent: number | null;
  money: Money;
  series: PaymentBucket[];
};
export type PlatformAnalytics = {
  range: DateRange;
  granularity: Granularity;
  new_customers: number;
  new_owners: number;
  new_venues: number;
  series: { bucket: string; customers: number; owners: number; venues_created: number }[];
  popular_categories: SportShare[];
  uncategorised_bookings: number;
  cities: CityShare[];
  top_venues: TopVenue[];
};

export type OwnerRow = {
  id: string;
  full_name: string;
  email: string | null;
  phone_masked: string | null;
  business_name: string;
  status: string;
  created_at: string;
  venues_count: number;
  published_venues_count: number;
  bookings_count: number;
};
export type VenueBrief = {
  id: string;
  name: string;
  status: string;
  city: string | null;
  created_at: string;
  bookings_count: number;
  confirmed_count: number;
};
export type OwnerDetail = {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  business_name: string;
  business_phone: string | null;
  business_email: string | null;
  business_address: string | null;
  status: string;
  created_at: string;
  venues: VenueBrief[];
  bookings_count: number;
  confirmed_count: number;
  gross_paid_paise: number;
  recent_bookings: BookingBrief[];
  kyc_status: string;
  kyc_reviewed_at: string | null;
  kyc_note: string | null;
  pending_kyc_documents: number;
  verified_venues: number;
  payouts_paid_paise: number;
  refunds_paise: number;
};
export type CustomerRow = {
  id: string;
  full_name: string;
  email: string | null;
  phone_masked: string | null;
  status: string;
  created_at: string;
  bookings_count: number;
  confirmed_count: number;
};
export type CustomerDetail = {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  status: string;
  created_at: string;
  bookings_count: number;
  confirmed_count: number;
  cancelled_count: number;
  gross_paid_paise: number;
  bookings: BookingBrief[];
  completed_count: number;
  refunded_paise: number;
  deletion_requested_at: string | null;
  language: string | null;
  has_open_dispute: boolean;
};
export type VenueRow = {
  id: string;
  name: string;
  owner_id: string;
  owner_name: string;
  business_name: string;
  categories: string[];
  city: string | null;
  address_line: string | null;
  status: string;
  created_at: string;
  published_at: string | null;
  bookings_count: number;
  confirmed_count: number;
  is_verified: boolean;
  submitted_at: string | null;
  status_reason: string | null;
  owner_kyc_status: string | null;
  open_reports: number;
};
export type VenueDetail = VenueRow & {
  description: string | null;
  contact_phone: string | null;
  timezone: string;
  resources_count: number;
  active_resources_count: number;
  gross_paid_paise: number;
  rating_avg: number | null;
  rating_count: number;
  verified_at: string | null;
  completed_count: number;
  cancelled_count: number;
  future_confirmed_count: number;
  performance: { month: string; bookings: number; completed: number; cancelled: number; gross_paid_paise: number }[];
  owner_earnings: Figure | Unavailable | null;
};

export type StatusEvent = { from_status: string | null; to_status: string; actor_role: string; reason: string | null; created_at: string };
export type PaymentRow = {
  id: string;
  booking_id: string;
  booking_code: string;
  booking_status: string;
  customer_id: string;
  venue_id: string;
  venue_name: string;
  amount_paise: number;
  currency: string;
  status: string;
  method: string | null;
  razorpay_order_id: string;
  razorpay_payment_id: string | null;
  failure_code: string | null;
  failure_reason: string | null;
  review_required: boolean;
  review_reason: string | null;
  created_at: string;
  captured_at: string | null;
  failed_at: string | null;
  refunded_paise: number;
  refund_in_flight_paise: number;
};
export type PaymentEvent = {
  id: string;
  event_type: string;
  source: string;
  outcome: string;
  provider_event_id: string | null;
  provider_payment_id: string | null;
  created_at: string;
};
export type PaymentDetail = PaymentRow & { events: PaymentEvent[]; refunds: Row[] };
export type PaymentSummary = {
  currency: string;
  gross_captured_paise: number;
  captured_count: number;
  failed_count: number;
  open_count: number;
  review_required_count: number;
  rejected_events_count: number;
  refunds: { processed_paise: number; processed_count: number; in_flight_count: number; failed_count: number };
};
export type BookingRow = {
  id: string;
  booking_code: string;
  status: string;
  payment_status: string;
  venue_id: string;
  venue_name: string;
  resource_name: string;
  booking_date: string;
  local_start: string;
  local_end: string;
  duration_minutes: number;
  currency: string;
  total_amount_paise: number;
  created_at: string;
  cancelled_at: string | null;
  cancel_reason: string | null;
  customer_id: string;
  customer_name: string;
  owner_id: string;
  owner_name: string;
  payment_amount_paise: number | null;
  payment_id: string | null;
  city: string | null;
  sports: string[];
  refund_status: string;
  refunded_paise: number;
  history: { from_status: string | null; to_status: string; actor_role: string; reason: string | null; created_at: string }[];
};
export type BookingDetail = BookingRow & {
  payments: PaymentRow[];
  customer: { id: string; full_name: string | null; email: string | null; phone: string | null; status: string | null } | null;
  owner: { id: string; full_name: string; email: string | null; phone: string | null; business_name: string | null; kyc_status: string | null; status: string } | null;
  venue: { id: string; name: string; address_line: string | null; city: string | null; status: string; is_verified: boolean; contact_phone: string | null; timezone: string } | null;
  price_snapshot: Record<string, unknown> | null;
  refunds: Row[];
  disputes: { id: string; subject: string; status: string; priority: string; created_at: string; resolution_type: string | null }[];
  coupon: { code: string | null; discount_paise: number } | null;
  timeline: { from_status: string | null; to_status: string; actor_role: string; actor_name: string | null; reason: string | null; created_at: string }[];
};

export type AppNotification = {
  id: string;
  type: string;
  title: string;
  body: string | null;
  is_read: boolean;
  created_at: string;
  booking_id: string | null;
  payment_id: string | null;
};
export type AuditRow = {
  id: string;
  action: string;
  actor_id: string | null;
  actor_role: string | null;
  actor_name?: string | null;
  entity_type: string | null;
  entity_id: string | null;
  metadata: Record<string, unknown>;
  request_id?: string | null;
  created_at: string;
};

// ---- Settings (GET /profiles/me, /notifications/preferences, /version)
export type MyProfile = {
  id: string;
  role: "admin" | "owner" | "customer";
  status: "active" | "suspended";
  full_name: string;
  email: string | null;
  phone: string | null;
  avatar_path: string | null;
  created_at: string;
  updated_at: string;
};
export type NotificationPreferences = { push_enabled: boolean; email_enabled: boolean };
export type ApiVersion = { name: string; version: string; api_version: string };

export type SportShare = { category: string; bookings: number; tagged_bookings: number; venues: number; gross_paid_paise: number };
export type CityShare = {
  city_id: string | null; city: string; venues: number; bookings: number; confirmed: number; completed: number; cancelled: number; gross_paid_paise: number;
};
export type VenuePerformance = {
  venue_id: string; name: string; city: string | null; status: string; bookings: number; confirmed: number; completed: number; cancelled: number;
  cancellation_rate_percent: number | null; gross_paid_paise: number; average_booking_paise: number | null; rating_avg: number | null; rating_count: number;
};

/** Loose shapes for the admin-operations endpoints (the API validates; pages only read what they show). */
export type Row = Record<string, unknown> & { id: string };
export type Cursor<T = Row> = { items: T[]; limit: number; offset: number; has_more: boolean };
