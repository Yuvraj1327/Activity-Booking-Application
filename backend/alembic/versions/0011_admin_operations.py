"""Admin operations: permissions, venue moderation, KYC, refunds, finance, support, disputes, coupons, CMS.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-22

Every new table has RLS enabled and NO grants for anon/authenticated: only the backend (direct
database role) reads or writes them. History / ledger tables are append-only (trigger).

Business decisions that stay OPEN (Q4, Q7-Q10, Q18, N11) are NOT answered here. They are
configuration rows that default to "off" / "not approved" (platform_settings, finance_configs).
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

BOOKING_STATUSES = (
    "'pending_payment','payment_failed','confirmed','expired','cancelled_by_customer',"
    "'cancelled_by_owner','cancelled_by_admin','completed','refund_pending','refunded'"
)
OLD_BOOKING_STATUSES = (
    "'pending_payment','payment_failed','confirmed','expired','cancelled_by_customer',"
    "'cancelled_by_owner','completed','refund_pending','refunded'"
)

NEW_TABLES = [
    "platform_settings",
    "admin_roles",
    "admin_profiles",
    "venue_moderation_events",
    "venue_reports",
    "owner_kyc_documents",
    "support_ticket_messages",
    "disputes",
    "dispute_events",
    "refunds",
    "finance_configs",
    "ledger_entries",
    "payouts",
    "reconciliation_runs",
    "reconciliation_items",
    "coupons",
    "coupon_redemptions",
    "cms_contents",
]
APPEND_ONLY = [
    "venue_moderation_events",
    "support_ticket_messages",
    "dispute_events",
    "ledger_entries",
    "reconciliation_items",
]
UPDATED_AT = [
    "admin_roles",
    "venue_reports",
    "owner_kyc_documents",
    "disputes",
    "refunds",
    "payouts",
    "coupons",
    "cms_contents",
]

UP = [
    # ------------------------------------------------------------------ generic append-only guard
    """
CREATE FUNCTION public.forbid_modification() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% rows cannot be modified or deleted', TG_TABLE_NAME
    USING ERRCODE = 'integrity_constraint_violation';
END
$$
""",
    # ------------------------------------------------------------------ platform switches
    """
CREATE TABLE public.platform_settings (
  key text PRIMARY KEY,
  value jsonb NOT NULL,
  updated_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_platform_settings_key CHECK (key IN
    ('venue_approval_required','refunds_enabled','payouts_enabled','payout_requires_kyc'))
)
""",
    # ------------------------------------------------------------------ admin roles
    """
CREATE TABLE public.admin_roles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  description text,
  permissions text[] NOT NULL DEFAULT '{}',
  is_system boolean NOT NULL DEFAULT false,
  created_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_admin_roles_name UNIQUE (name),
  CONSTRAINT ck_admin_roles_name CHECK (char_length(btrim(name)) BETWEEN 2 AND 60),
  CONSTRAINT ck_admin_roles_perms CHECK (cardinality(permissions) <= 100)
)
""",
    """
CREATE TABLE public.admin_profiles (
  user_id uuid PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
  role_id uuid NOT NULL REFERENCES public.admin_roles(id) ON DELETE RESTRICT,
  assigned_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  assigned_at timestamptz NOT NULL DEFAULT now()
)
""",
    "CREATE INDEX ix_admin_profiles_role ON public.admin_profiles (role_id)",
    # The built-in role keeps every permission the code defines (resolved at run time).
    "INSERT INTO public.admin_roles (name, description, permissions, is_system) VALUES "
    "('super_admin', 'Every permission. Assignable only by an existing super_admin.', '{}', true)",
    # Existing admins keep exactly the access they have today.
    "INSERT INTO public.admin_profiles (user_id, role_id) "
    "SELECT p.id, r.id FROM public.profiles p, public.admin_roles r "
    "WHERE p.role = 'admin' AND r.name = 'super_admin'",
    # ------------------------------------------------------------------ venues: approval + verification
    "ALTER TABLE public.venues DROP CONSTRAINT ck_venues_status",
    "ALTER TABLE public.venues ADD CONSTRAINT ck_venues_status CHECK "
    "(status IN ('draft','pending_review','published','rejected','suspended','archived'))",
    "ALTER TABLE public.venues ADD COLUMN is_verified boolean NOT NULL DEFAULT false, "
    "ADD COLUMN verified_at timestamptz, "
    "ADD COLUMN verified_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL, "
    "ADD COLUMN status_reason text, ADD COLUMN submitted_at timestamptz",
    """
CREATE TABLE public.venue_moderation_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  venue_id uuid NOT NULL REFERENCES public.venues(id) ON DELETE CASCADE,
  action text NOT NULL,
  from_status text,
  to_status text,
  reason text,
  actor_id uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  actor_role text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_vme_action CHECK (action IN
    ('submitted','approved','rejected','verified','unverified','suspended','reinstated','withdrawn')),
  CONSTRAINT ck_vme_actor CHECK (actor_role IN ('owner','admin','system'))
)
""",
    "CREATE INDEX ix_vme_venue ON public.venue_moderation_events (venue_id, created_at DESC)",
    """
CREATE TABLE public.venue_reports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  venue_id uuid NOT NULL REFERENCES public.venues(id) ON DELETE CASCADE,
  reporter_id uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  reason text NOT NULL,
  details text,
  status text NOT NULL DEFAULT 'open',
  resolution_note text,
  resolved_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  resolved_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_venue_reports_reason CHECK (reason IN
    ('inaccurate_info','unsafe','fraud','inappropriate','other')),
  CONSTRAINT ck_venue_reports_status CHECK (status IN ('open','reviewing','dismissed','action_taken')),
  CONSTRAINT ck_venue_reports_details CHECK (details IS NULL OR char_length(details) <= 1000)
)
""",
    "CREATE INDEX ix_venue_reports_status ON public.venue_reports (status, created_at DESC)",
    "CREATE INDEX ix_venue_reports_venue ON public.venue_reports (venue_id)",
    "CREATE UNIQUE INDEX uq_venue_reports_open ON public.venue_reports (venue_id, reporter_id) "
    "WHERE status IN ('open','reviewing') AND reporter_id IS NOT NULL",
    # ------------------------------------------------------------------ owner KYC
    "ALTER TABLE public.owner_profiles ADD COLUMN kyc_status text NOT NULL DEFAULT 'not_submitted', "
    "ADD COLUMN kyc_reviewed_at timestamptz, "
    "ADD COLUMN kyc_reviewed_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL, "
    "ADD COLUMN kyc_note text",
    "ALTER TABLE public.owner_profiles ADD CONSTRAINT ck_owner_profiles_kyc "
    "CHECK (kyc_status IN ('not_submitted','pending','verified','rejected'))",
    """
CREATE TABLE public.owner_kyc_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL REFERENCES public.owner_profiles(user_id) ON DELETE CASCADE,
  doc_type text NOT NULL,
  storage_path text NOT NULL,
  original_filename text,
  content_type text NOT NULL,
  byte_size bigint NOT NULL,
  status text NOT NULL DEFAULT 'pending',
  rejection_reason text,
  reviewed_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  reviewed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_kyc_storage_path UNIQUE (storage_path),
  CONSTRAINT ck_kyc_doc_type CHECK (doc_type IN
    ('identity','address','business_registration','gst','bank_account','other')),
  CONSTRAINT ck_kyc_status CHECK (status IN ('pending','approved','rejected')),
  CONSTRAINT ck_kyc_content_type CHECK (content_type IN ('application/pdf','image/jpeg','image/png')),
  CONSTRAINT ck_kyc_size CHECK (byte_size BETWEEN 1 AND 5242880),
  CONSTRAINT ck_kyc_rejection CHECK (status <> 'rejected' OR rejection_reason IS NOT NULL)
)
""",
    "CREATE INDEX ix_kyc_owner ON public.owner_kyc_documents (owner_id, created_at DESC)",
    "CREATE INDEX ix_kyc_pending ON public.owner_kyc_documents (created_at) WHERE status = 'pending'",
    # Private bucket: no public read, no client policy on storage.objects (backend service role only).
    "INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types) VALUES "
    "('kyc-documents', 'kyc-documents', false, 5242880, ARRAY['application/pdf','image/jpeg','image/png']) "
    "ON CONFLICT (id) DO UPDATE SET public = false, file_size_limit = EXCLUDED.file_size_limit, "
    "allowed_mime_types = EXCLUDED.allowed_mime_types",
    # ------------------------------------------------------------------ bookings: admin cancel, partial refunds
    "ALTER TABLE public.bookings DROP CONSTRAINT ck_bookings_status",
    f"ALTER TABLE public.bookings ADD CONSTRAINT ck_bookings_status CHECK (status IN ({BOOKING_STATUSES}))",
    "ALTER TABLE public.bookings DROP CONSTRAINT ck_bookings_payment_status",
    "ALTER TABLE public.bookings ADD CONSTRAINT ck_bookings_payment_status CHECK "
    "(payment_status IN ('unpaid','pending','paid','failed','refunded','partially_refunded'))",
    "ALTER TABLE public.booking_status_history DROP CONSTRAINT ck_bsh_to",
    f"ALTER TABLE public.booking_status_history ADD CONSTRAINT ck_bsh_to CHECK (to_status IN ({BOOKING_STATUSES}))",
    # ------------------------------------------------------------------ support tickets
    "ALTER TABLE public.support_tickets DROP CONSTRAINT ck_support_tickets_status",
    "ALTER TABLE public.support_tickets ADD CONSTRAINT ck_support_tickets_status "
    "CHECK (status IN ('open','in_progress','resolved','closed'))",
    "ALTER TABLE public.support_tickets ADD COLUMN priority text NOT NULL DEFAULT 'normal', "
    "ADD COLUMN booking_id uuid REFERENCES public.bookings(id) ON DELETE SET NULL, "
    "ADD COLUMN assigned_to uuid REFERENCES public.profiles(id) ON DELETE SET NULL, "
    "ADD COLUMN resolved_at timestamptz",
    "ALTER TABLE public.support_tickets ADD CONSTRAINT ck_support_tickets_priority "
    "CHECK (priority IN ('low','normal','high','urgent'))",
    "CREATE INDEX ix_support_tickets_status ON public.support_tickets (status, created_at DESC)",
    """
CREATE TABLE public.support_ticket_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id uuid NOT NULL REFERENCES public.support_tickets(id) ON DELETE CASCADE,
  author_id uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  author_role text NOT NULL,
  kind text NOT NULL,
  body text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_stm_role CHECK (author_role IN ('customer','owner','admin','system')),
  CONSTRAINT ck_stm_kind CHECK (kind IN ('reply','note','event')),
  CONSTRAINT ck_stm_body CHECK (char_length(btrim(body)) BETWEEN 1 AND 4000)
)
""",
    "CREATE INDEX ix_stm_ticket ON public.support_ticket_messages (ticket_id, created_at)",
    # ------------------------------------------------------------------ disputes
    """
CREATE TABLE public.disputes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id uuid NOT NULL REFERENCES public.bookings(id) ON DELETE RESTRICT,
  payment_id uuid REFERENCES public.payments(id) ON DELETE SET NULL,
  raised_by_role text NOT NULL,
  raised_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  subject text NOT NULL,
  description text,
  status text NOT NULL DEFAULT 'open',
  priority text NOT NULL DEFAULT 'normal',
  resolution_type text,
  resolution_note text,
  resolved_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  resolved_at timestamptz,
  created_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_disputes_role CHECK (raised_by_role IN ('customer','owner','admin')),
  CONSTRAINT ck_disputes_status CHECK (status IN ('open','investigating','resolved','rejected')),
  CONSTRAINT ck_disputes_priority CHECK (priority IN ('low','normal','high','urgent')),
  CONSTRAINT ck_disputes_resolution CHECK (resolution_type IS NULL OR resolution_type IN
    ('no_action','refund_full','refund_partial','booking_cancelled','other')),
  CONSTRAINT ck_disputes_closed CHECK (status NOT IN ('resolved','rejected')
    OR (resolution_note IS NOT NULL AND resolved_at IS NOT NULL)),
  CONSTRAINT ck_disputes_subject CHECK (char_length(btrim(subject)) BETWEEN 3 AND 160)
)
""",
    "CREATE INDEX ix_disputes_status ON public.disputes (status, created_at DESC)",
    "CREATE INDEX ix_disputes_booking ON public.disputes (booking_id)",
    "CREATE UNIQUE INDEX uq_disputes_one_active ON public.disputes (booking_id) "
    "WHERE status IN ('open','investigating')",
    """
CREATE TABLE public.dispute_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dispute_id uuid NOT NULL REFERENCES public.disputes(id) ON DELETE CASCADE,
  kind text NOT NULL,
  body text,
  data jsonb NOT NULL DEFAULT '{}'::jsonb,
  actor_id uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  actor_role text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_dispute_events_kind CHECK (kind IN
    ('opened','note','evidence','status_changed','priority_changed','action','resolved')),
  CONSTRAINT ck_dispute_events_data CHECK (jsonb_typeof(data) = 'object')
)
""",
    "CREATE INDEX ix_dispute_events_dispute ON public.dispute_events (dispute_id, created_at)",
    # ------------------------------------------------------------------ refunds
    """
CREATE TABLE public.refunds (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  payment_id uuid NOT NULL REFERENCES public.payments(id) ON DELETE RESTRICT,
  booking_id uuid NOT NULL REFERENCES public.bookings(id) ON DELETE RESTRICT,
  dispute_id uuid REFERENCES public.disputes(id) ON DELETE SET NULL,
  amount_paise bigint NOT NULL,
  currency text NOT NULL DEFAULT 'INR',
  status text NOT NULL DEFAULT 'requested',
  source text NOT NULL DEFAULT 'admin',
  idempotency_key text,
  provider_refund_id text,
  reason text,
  failure_reason text,
  initiated_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  processed_at timestamptz,
  CONSTRAINT ck_refunds_amount CHECK (amount_paise > 0),
  CONSTRAINT ck_refunds_status CHECK (status IN ('requested','pending','processed','failed','uncertain')),
  CONSTRAINT ck_refunds_source CHECK (source IN ('admin','gateway')),
  CONSTRAINT ck_refunds_key CHECK (idempotency_key IS NULL OR char_length(idempotency_key) BETWEEN 8 AND 100)
)
""",
    "CREATE UNIQUE INDEX uq_refunds_provider ON public.refunds (provider_refund_id) "
    "WHERE provider_refund_id IS NOT NULL",
    "CREATE UNIQUE INDEX uq_refunds_idem ON public.refunds (payment_id, idempotency_key) "
    "WHERE idempotency_key IS NOT NULL",
    "CREATE INDEX ix_refunds_payment ON public.refunds (payment_id)",
    "CREATE INDEX ix_refunds_status ON public.refunds (status, created_at DESC)",
    # ------------------------------------------------------------------ finance configuration (versioned)
    """
CREATE TABLE public.finance_configs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  version integer GENERATED ALWAYS AS IDENTITY,
  status text NOT NULL DEFAULT 'draft',
  platform_fee_bps integer NOT NULL DEFAULT 0,
  platform_fee_fixed_paise bigint NOT NULL DEFAULT 0,
  tax_rate_bps integer NOT NULL DEFAULT 0,
  tax_on text NOT NULL,
  commission_bps integer NOT NULL DEFAULT 0,
  discount_borne_by text NOT NULL,
  notes text,
  created_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  approved_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  approved_at timestamptz,
  effective_from timestamptz,
  retired_at timestamptz,
  CONSTRAINT uq_finance_configs_version UNIQUE (version),
  CONSTRAINT ck_finance_status CHECK (status IN ('draft','approved','retired')),
  CONSTRAINT ck_finance_fee_bps CHECK (platform_fee_bps BETWEEN 0 AND 10000),
  CONSTRAINT ck_finance_fee_fixed CHECK (platform_fee_fixed_paise BETWEEN 0 AND 100000000),
  CONSTRAINT ck_finance_tax_bps CHECK (tax_rate_bps BETWEEN 0 AND 10000),
  CONSTRAINT ck_finance_commission CHECK (commission_bps BETWEEN 0 AND 10000),
  CONSTRAINT ck_finance_tax_on CHECK (tax_on IN ('fee','base_and_fee')),
  CONSTRAINT ck_finance_discount CHECK (discount_borne_by IN ('platform','owner')),
  CONSTRAINT ck_finance_approved CHECK (status = 'draft' OR (approved_by IS NOT NULL AND effective_from IS NOT NULL))
)
""",
    # An approved configuration is immutable. Only the retire step (status + retired_at) may change it.
    """
CREATE FUNCTION public.finance_configs_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.status <> 'draft' THEN
      RAISE EXCEPTION 'approved finance configurations cannot be deleted'
        USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN OLD;
  END IF;
  IF OLD.status = 'draft' THEN
    RETURN NEW;
  END IF;
  IF OLD.status = 'approved' AND NEW.status = 'retired'
     AND (to_jsonb(NEW) - 'status' - 'retired_at') = (to_jsonb(OLD) - 'status' - 'retired_at') THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'approved finance configurations are immutable'
    USING ERRCODE = 'integrity_constraint_violation';
END
$$
""",
    "CREATE TRIGGER trg_finance_configs_guard BEFORE UPDATE OR DELETE ON public.finance_configs "
    "FOR EACH ROW EXECUTE FUNCTION public.finance_configs_guard()",
    "CREATE INDEX ix_finance_effective ON public.finance_configs (effective_from DESC) WHERE status <> 'draft'",
    # ------------------------------------------------------------------ payouts
    """
CREATE TABLE public.payouts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL REFERENCES public.owner_profiles(user_id) ON DELETE RESTRICT,
  amount_paise bigint NOT NULL,
  currency text NOT NULL DEFAULT 'INR',
  status text NOT NULL DEFAULT 'draft',
  period_from date,
  period_to date,
  method text,
  reference text,
  note text,
  created_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  approved_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  approved_at timestamptz,
  paid_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  paid_at timestamptz,
  cancel_reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_payouts_amount CHECK (amount_paise > 0),
  CONSTRAINT ck_payouts_status CHECK (status IN ('draft','approved','paid','cancelled')),
  CONSTRAINT ck_payouts_period CHECK (period_from IS NULL OR period_to IS NULL OR period_from <= period_to),
  CONSTRAINT ck_payouts_paid CHECK (status <> 'paid' OR (reference IS NOT NULL AND paid_at IS NOT NULL)),
  CONSTRAINT ck_payouts_cancel CHECK (status <> 'cancelled' OR cancel_reason IS NOT NULL)
)
""",
    "CREATE INDEX ix_payouts_owner ON public.payouts (owner_id, created_at DESC)",
    "CREATE INDEX ix_payouts_status ON public.payouts (status, created_at DESC)",
    # ------------------------------------------------------------------ ledger (immutable)
    """
CREATE TABLE public.ledger_entries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entry_key text NOT NULL,
  kind text NOT NULL,
  owner_id uuid NOT NULL REFERENCES public.owner_profiles(user_id) ON DELETE RESTRICT,
  venue_id uuid NOT NULL REFERENCES public.venues(id) ON DELETE RESTRICT,
  booking_id uuid NOT NULL REFERENCES public.bookings(id) ON DELETE RESTRICT,
  payment_id uuid NOT NULL REFERENCES public.payments(id) ON DELETE RESTRICT,
  refund_id uuid REFERENCES public.refunds(id) ON DELETE RESTRICT,
  config_id uuid NOT NULL REFERENCES public.finance_configs(id) ON DELETE RESTRICT,
  config_version integer NOT NULL,
  gross_paise bigint NOT NULL,
  tax_paise bigint NOT NULL,
  owner_amount_paise bigint NOT NULL,
  platform_amount_paise bigint NOT NULL,
  fee_paise bigint NOT NULL DEFAULT 0,
  commission_paise bigint NOT NULL DEFAULT 0,
  discount_paise bigint NOT NULL DEFAULT 0,
  occurred_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_ledger_entry_key UNIQUE (entry_key),
  CONSTRAINT ck_ledger_kind CHECK (kind IN ('sale','refund')),
  CONSTRAINT ck_ledger_balanced CHECK (gross_paise = owner_amount_paise + platform_amount_paise + tax_paise)
)
""",
    "CREATE INDEX ix_ledger_owner ON public.ledger_entries (owner_id, occurred_at DESC)",
    "CREATE INDEX ix_ledger_occurred ON public.ledger_entries (occurred_at DESC)",
    "CREATE INDEX ix_ledger_payment ON public.ledger_entries (payment_id)",
    # ------------------------------------------------------------------ reconciliation
    """
CREATE TABLE public.reconciliation_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  period_from date NOT NULL,
  period_to date NOT NULL,
  gateway_checked boolean NOT NULL DEFAULT false,
  gateway_note text,
  summary jsonb NOT NULL DEFAULT '{}'::jsonb,
  mismatch_count integer NOT NULL DEFAULT 0,
  run_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_recon_period CHECK (period_from <= period_to),
  CONSTRAINT ck_recon_summary CHECK (jsonb_typeof(summary) = 'object')
)
""",
    """
CREATE TABLE public.reconciliation_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES public.reconciliation_runs(id) ON DELETE CASCADE,
  kind text NOT NULL,
  payment_id uuid REFERENCES public.payments(id) ON DELETE SET NULL,
  refund_id uuid REFERENCES public.refunds(id) ON DELETE SET NULL,
  provider_payment_id text,
  expected_paise bigint,
  actual_paise bigint,
  detail text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_recon_items_kind CHECK (kind IN (
    'missing_in_gateway','missing_in_database','amount_mismatch','status_mismatch',
    'refund_mismatch','ledger_missing','ledger_mismatch','refund_stuck'))
)
""",
    "CREATE INDEX ix_recon_items_run ON public.reconciliation_items (run_id)",
    # ------------------------------------------------------------------ coupons
    """
CREATE TABLE public.coupons (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text NOT NULL,
  description text,
  discount_type text NOT NULL,
  percent_bps integer,
  fixed_paise bigint,
  max_discount_paise bigint,
  min_booking_paise bigint NOT NULL DEFAULT 0,
  valid_from timestamptz,
  valid_until timestamptz,
  usage_limit_total integer,
  usage_limit_per_user integer,
  first_booking_only boolean NOT NULL DEFAULT false,
  eligible_category_ids uuid[] NOT NULL DEFAULT '{}',
  eligible_city_ids uuid[] NOT NULL DEFAULT '{}',
  eligible_venue_ids uuid[] NOT NULL DEFAULT '{}',
  is_active boolean NOT NULL DEFAULT true,
  created_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_coupons_code UNIQUE (code),
  CONSTRAINT ck_coupons_code CHECK (code ~ '^[A-Z0-9_-]{3,30}$'),
  CONSTRAINT ck_coupons_type CHECK (discount_type IN ('percent','fixed')),
  CONSTRAINT ck_coupons_value CHECK (
    (discount_type = 'percent' AND percent_bps BETWEEN 1 AND 10000 AND fixed_paise IS NULL)
    OR (discount_type = 'fixed' AND fixed_paise > 0 AND percent_bps IS NULL)),
  CONSTRAINT ck_coupons_max CHECK (max_discount_paise IS NULL OR max_discount_paise > 0),
  CONSTRAINT ck_coupons_min CHECK (min_booking_paise >= 0),
  CONSTRAINT ck_coupons_window CHECK (valid_from IS NULL OR valid_until IS NULL OR valid_from < valid_until),
  CONSTRAINT ck_coupons_limits CHECK (
    (usage_limit_total IS NULL OR usage_limit_total > 0) AND
    (usage_limit_per_user IS NULL OR usage_limit_per_user > 0))
)
""",
    """
CREATE TABLE public.coupon_redemptions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  coupon_id uuid NOT NULL REFERENCES public.coupons(id) ON DELETE RESTRICT,
  booking_id uuid NOT NULL REFERENCES public.bookings(id) ON DELETE RESTRICT,
  customer_id uuid NOT NULL REFERENCES public.customer_profiles(user_id) ON DELETE RESTRICT,
  discount_paise bigint NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_coupon_redemptions_booking UNIQUE (booking_id),
  CONSTRAINT ck_coupon_redemptions_amount CHECK (discount_paise > 0)
)
""",
    "CREATE INDEX ix_coupon_redemptions_coupon ON public.coupon_redemptions (coupon_id, customer_id)",
    # ------------------------------------------------------------------ CMS
    """
CREATE TABLE public.cms_contents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind text NOT NULL,
  slug text NOT NULL,
  audience text NOT NULL DEFAULT 'all',
  title text NOT NULL,
  body text NOT NULL,
  sort_order integer NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'draft',
  published_at timestamptz,
  updated_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_cms_slug UNIQUE (slug),
  CONSTRAINT ck_cms_kind CHECK (kind IN ('page','faq')),
  CONSTRAINT ck_cms_slug CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND char_length(slug) <= 80),
  CONSTRAINT ck_cms_audience CHECK (audience IN ('all','customer','owner')),
  CONSTRAINT ck_cms_status CHECK (status IN ('draft','published')),
  CONSTRAINT ck_cms_title CHECK (char_length(btrim(title)) BETWEEN 1 AND 200),
  CONSTRAINT ck_cms_body CHECK (char_length(body) BETWEEN 1 AND 50000)
)
""",
    "CREATE INDEX ix_cms_published ON public.cms_contents (kind, audience, sort_order) WHERE status = 'published'",
]


def _tail() -> list[str]:
    out: list[str] = []
    for t in UPDATED_AT:
        out.append(
            f"CREATE TRIGGER trg_{t}_set_updated_at BEFORE UPDATE ON public.{t} "
            "FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()"
        )
    for t in APPEND_ONLY:
        out.append(
            f"CREATE TRIGGER trg_{t}_append_only BEFORE UPDATE OR DELETE ON public.{t} "
            "FOR EACH ROW EXECUTE FUNCTION public.forbid_modification()"
        )
    for t in NEW_TABLES:
        out.append(f"ALTER TABLE public.{t} ENABLE ROW LEVEL SECURITY")
        out.append(f"REVOKE ALL ON public.{t} FROM anon, authenticated")
    return out


STATEMENTS = UP + _tail()


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for t in reversed(NEW_TABLES):
        op.execute(f"DROP TABLE IF EXISTS public.{t} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS public.finance_configs_guard()")
    op.execute("DROP FUNCTION IF EXISTS public.forbid_modification()")
    op.execute("DELETE FROM storage.buckets WHERE id = 'kyc-documents'")
    op.execute("ALTER TABLE public.support_tickets DROP COLUMN IF EXISTS resolved_at, "
               "DROP COLUMN IF EXISTS assigned_to, DROP COLUMN IF EXISTS booking_id, "
               "DROP COLUMN IF EXISTS priority")
    op.execute("ALTER TABLE public.support_tickets DROP CONSTRAINT IF EXISTS ck_support_tickets_status")
    op.execute("UPDATE public.support_tickets SET status = 'open' WHERE status = 'in_progress'")
    op.execute("UPDATE public.support_tickets SET status = 'closed' WHERE status = 'resolved'")
    op.execute("ALTER TABLE public.support_tickets ADD CONSTRAINT ck_support_tickets_status "
               "CHECK (status IN ('open','closed'))")
    op.execute("ALTER TABLE public.booking_status_history DROP CONSTRAINT IF EXISTS ck_bsh_to")
    op.execute("ALTER TABLE public.bookings DROP CONSTRAINT IF EXISTS ck_bookings_status")
    op.execute("ALTER TABLE public.bookings DROP CONSTRAINT IF EXISTS ck_bookings_payment_status")
    op.execute("UPDATE public.bookings SET status = 'cancelled_by_owner' WHERE status = 'cancelled_by_admin'")
    op.execute("ALTER TABLE public.booking_status_history DISABLE TRIGGER trg_bsh_no_update")
    op.execute("UPDATE public.booking_status_history SET to_status = 'cancelled_by_owner' "
               "WHERE to_status = 'cancelled_by_admin'")
    op.execute("ALTER TABLE public.booking_status_history ENABLE TRIGGER trg_bsh_no_update")
    op.execute(f"ALTER TABLE public.bookings ADD CONSTRAINT ck_bookings_status CHECK (status IN ({OLD_BOOKING_STATUSES}))")
    op.execute("ALTER TABLE public.bookings ADD CONSTRAINT ck_bookings_payment_status CHECK "
               "(payment_status IN ('unpaid','pending','paid','failed','refunded'))")
    op.execute(f"ALTER TABLE public.booking_status_history ADD CONSTRAINT ck_bsh_to CHECK (to_status IN ({OLD_BOOKING_STATUSES}))")
    op.execute("ALTER TABLE public.owner_profiles DROP CONSTRAINT IF EXISTS ck_owner_profiles_kyc")
    op.execute("ALTER TABLE public.owner_profiles DROP COLUMN IF EXISTS kyc_note, "
               "DROP COLUMN IF EXISTS kyc_reviewed_by, DROP COLUMN IF EXISTS kyc_reviewed_at, "
               "DROP COLUMN IF EXISTS kyc_status")
    op.execute("ALTER TABLE public.venues DROP CONSTRAINT IF EXISTS ck_venues_status")
    op.execute("UPDATE public.venues SET status = 'draft' WHERE status IN ('pending_review','rejected','suspended')")
    op.execute("ALTER TABLE public.venues ADD CONSTRAINT ck_venues_status CHECK "
               "(status IN ('draft','published','archived'))")
    op.execute("ALTER TABLE public.venues DROP COLUMN IF EXISTS submitted_at, "
               "DROP COLUMN IF EXISTS status_reason, DROP COLUMN IF EXISTS verified_by, "
               "DROP COLUMN IF EXISTS verified_at, DROP COLUMN IF EXISTS is_verified")
