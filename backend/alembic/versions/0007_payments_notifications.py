"""Payments (Razorpay), payment events, notifications upgrade, device tokens, email log (Step 7).

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-12

* `payments`: ONE row per booking (UNIQUE booking_id) and per gateway order. That is the database
  guarantee against duplicate payments; retries after a failed attempt reuse the same order.
  Amounts are copied from the booking on the server; the client never supplies one.
* `payment_events`: append-only audit of every gateway signal (webhook / verify / reconcile). The
  gateway event id is UNIQUE, which makes webhook processing idempotent.
* Refunds and payouts are NOT modelled: no refund or payout policy is approved (Q9, Q10).
* `notifications` gains related booking/payment ids, a de-duplication key and push delivery state.
* `user_device_tokens`, `notification_preferences`, `email_deliveries` support FCM and Resend.
  Card numbers, CVV and gateway secrets are never stored anywhere.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PAYMENT_STATUSES = "'created','pending','authorized','captured','failed','refunded','partially_refunded'"

UP = [
    f"""
CREATE TABLE public.payments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id uuid NOT NULL REFERENCES public.bookings(id) ON DELETE RESTRICT,
  customer_id uuid NOT NULL REFERENCES public.customer_profiles(user_id) ON DELETE RESTRICT,
  venue_id uuid NOT NULL REFERENCES public.venues(id) ON DELETE RESTRICT,
  provider text NOT NULL DEFAULT 'razorpay',
  provider_order_id text NOT NULL,
  provider_payment_id text,
  amount_paise bigint NOT NULL,
  currency text NOT NULL,
  status text NOT NULL DEFAULT 'created',
  method text,
  failure_code text,
  failure_reason text,
  review_required boolean NOT NULL DEFAULT false,
  review_reason text,
  gateway_refs jsonb NOT NULL DEFAULT '{{}}'::jsonb,
  captured_at timestamptz,
  failed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_payments_status CHECK (status IN ({PAYMENT_STATUSES})),
  CONSTRAINT ck_payments_amount CHECK (amount_paise > 0),
  CONSTRAINT ck_payments_provider CHECK (provider IN ('razorpay')),
  CONSTRAINT ck_payments_captured CHECK (
    status NOT IN ('captured','refunded','partially_refunded') OR provider_payment_id IS NOT NULL),
  CONSTRAINT ck_payments_refs CHECK (jsonb_typeof(gateway_refs) = 'object'),
  CONSTRAINT ck_payments_review CHECK (NOT review_required OR review_reason IS NOT NULL)
)
""",
    "CREATE UNIQUE INDEX uq_payments_booking ON public.payments (booking_id)",
    "CREATE UNIQUE INDEX uq_payments_order ON public.payments (provider, provider_order_id)",
    "CREATE UNIQUE INDEX uq_payments_provider_payment ON public.payments (provider, provider_payment_id) "
    "WHERE provider_payment_id IS NOT NULL",
    "CREATE INDEX ix_payments_customer ON public.payments (customer_id, created_at DESC)",
    "CREATE INDEX ix_payments_venue ON public.payments (venue_id, created_at DESC)",
    "CREATE INDEX ix_payments_status ON public.payments (status, created_at)",
    "CREATE INDEX ix_payments_review ON public.payments (created_at) WHERE review_required",
    "CREATE TRIGGER trg_payments_updated BEFORE UPDATE ON public.payments "
    "FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()",
    # ---- gateway signals (append-only)
    """
CREATE TABLE public.payment_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  payment_id uuid REFERENCES public.payments(id) ON DELETE CASCADE,
  provider_event_id text,
  event_type text NOT NULL,
  source text NOT NULL,
  provider_order_id text,
  provider_payment_id text,
  outcome text NOT NULL,
  detail jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_payment_events_source CHECK (source IN ('webhook','verify','reconcile','system')),
  CONSTRAINT ck_payment_events_outcome CHECK (outcome IN ('applied','duplicate','ignored','rejected')),
  CONSTRAINT ck_payment_events_detail CHECK (jsonb_typeof(detail) = 'object')
)
""",
    "CREATE UNIQUE INDEX uq_payment_events_provider_event ON public.payment_events (provider_event_id) "
    "WHERE provider_event_id IS NOT NULL",
    "CREATE INDEX ix_payment_events_payment ON public.payment_events (payment_id, created_at)",
    "CREATE INDEX ix_payment_events_outcome ON public.payment_events (outcome, created_at DESC)",
    """
CREATE FUNCTION public.payment_events_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'payment_events rows cannot be modified' USING ERRCODE = 'integrity_constraint_violation';
END $$
""",
    "CREATE TRIGGER trg_payment_events_no_update BEFORE UPDATE ON public.payment_events "
    "FOR EACH ROW EXECUTE FUNCTION public.payment_events_append_only()",
    # ---- notifications: related ids, de-duplication, push delivery state
    "ALTER TABLE public.notifications "
    "ADD COLUMN booking_id uuid REFERENCES public.bookings(id) ON DELETE SET NULL, "
    "ADD COLUMN payment_id uuid REFERENCES public.payments(id) ON DELETE SET NULL, "
    "ADD COLUMN dedupe_key text, "
    "ADD COLUMN push_status text NOT NULL DEFAULT 'skipped', "
    "ADD COLUMN push_attempts integer NOT NULL DEFAULT 0, "
    "ADD COLUMN push_sent_at timestamptz",
    "ALTER TABLE public.notifications ADD CONSTRAINT ck_notifications_push_status "
    "CHECK (push_status IN ('pending','sent','failed','skipped'))",
    "CREATE UNIQUE INDEX uq_notifications_dedupe ON public.notifications (user_id, dedupe_key) "
    "WHERE dedupe_key IS NOT NULL",
    "CREATE INDEX ix_notifications_push_pending ON public.notifications (created_at) "
    "WHERE push_status = 'pending'",
    # ---- device tokens and preferences
    """
CREATE TABLE public.user_device_tokens (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  token text NOT NULL,
  platform text NOT NULL,
  app text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_device_tokens_platform CHECK (platform IN ('android','ios','web')),
  CONSTRAINT ck_device_tokens_app CHECK (app IN ('customer','owner','admin')),
  CONSTRAINT ck_device_tokens_token CHECK (char_length(token) BETWEEN 20 AND 4096)
)
""",
    "CREATE UNIQUE INDEX uq_device_tokens_token ON public.user_device_tokens (token)",
    "CREATE INDEX ix_device_tokens_user ON public.user_device_tokens (user_id)",
    "CREATE TRIGGER trg_device_tokens_updated BEFORE UPDATE ON public.user_device_tokens "
    "FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()",
    """
CREATE TABLE public.notification_preferences (
  user_id uuid PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
  push_enabled boolean NOT NULL DEFAULT true,
  email_enabled boolean NOT NULL DEFAULT true,
  updated_at timestamptz NOT NULL DEFAULT now()
)
""",
    "CREATE TRIGGER trg_notification_preferences_updated BEFORE UPDATE ON public.notification_preferences "
    "FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()",
    # ---- email delivery log (also the retry queue)
    """
CREATE TABLE public.email_deliveries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  to_email text NOT NULL,
  template text NOT NULL,
  context jsonb NOT NULL DEFAULT '{}'::jsonb,
  dedupe_key text NOT NULL,
  status text NOT NULL DEFAULT 'queued',
  attempts integer NOT NULL DEFAULT 0,
  provider_message_id text,
  last_error text,
  booking_id uuid REFERENCES public.bookings(id) ON DELETE SET NULL,
  payment_id uuid REFERENCES public.payments(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  sent_at timestamptz,
  CONSTRAINT ck_email_deliveries_status CHECK (status IN ('queued','sent','failed','skipped')),
  CONSTRAINT ck_email_deliveries_context CHECK (jsonb_typeof(context) = 'object')
)
""",
    "CREATE UNIQUE INDEX uq_email_deliveries_dedupe ON public.email_deliveries (dedupe_key)",
    "CREATE INDEX ix_email_deliveries_queue ON public.email_deliveries (created_at) WHERE status = 'queued'",
    "CREATE TRIGGER trg_email_deliveries_updated BEFORE UPDATE ON public.email_deliveries "
    "FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()",
    # ---- security model as before: RLS on, SELECT-only for clients, writes only through the API
    "ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.payment_events ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.user_device_tokens ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.notification_preferences ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.email_deliveries ENABLE ROW LEVEL SECURITY",
    "REVOKE ALL ON public.payments, public.payment_events, public.user_device_tokens, "
    "public.notification_preferences, public.email_deliveries FROM anon, authenticated",
    # device tokens and the email queue are never readable by clients
    "GRANT SELECT ON public.payments, public.notification_preferences TO authenticated",
    "CREATE POLICY payments_select_own ON public.payments FOR SELECT TO authenticated "
    "USING (customer_id = (SELECT auth.uid()))",
    "CREATE POLICY payments_select_owner ON public.payments FOR SELECT TO authenticated "
    "USING ((SELECT public.app_user_role()) = 'owner' AND EXISTS "
    "(SELECT 1 FROM public.venues v WHERE v.id = venue_id AND v.owner_id = (SELECT auth.uid())))",
    "CREATE POLICY payments_select_admin ON public.payments FOR SELECT TO authenticated "
    "USING ((SELECT public.app_user_role()) = 'admin')",
    "CREATE POLICY notification_preferences_select_own ON public.notification_preferences "
    "FOR SELECT TO authenticated USING (user_id = (SELECT auth.uid()))",
]


def upgrade() -> None:
    for statement in UP:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.email_deliveries CASCADE")
    op.execute("DROP TABLE IF EXISTS public.notification_preferences CASCADE")
    op.execute("DROP TABLE IF EXISTS public.user_device_tokens CASCADE")
    op.execute("DROP INDEX IF EXISTS public.ix_notifications_push_pending")
    op.execute("DROP INDEX IF EXISTS public.uq_notifications_dedupe")
    op.execute("ALTER TABLE public.notifications DROP CONSTRAINT IF EXISTS ck_notifications_push_status")
    op.execute(
        "ALTER TABLE public.notifications DROP COLUMN IF EXISTS push_sent_at, "
        "DROP COLUMN IF EXISTS push_attempts, DROP COLUMN IF EXISTS push_status, "
        "DROP COLUMN IF EXISTS dedupe_key, DROP COLUMN IF EXISTS payment_id, "
        "DROP COLUMN IF EXISTS booking_id"
    )
    op.execute("DROP TABLE IF EXISTS public.payment_events CASCADE")
    op.execute("DROP FUNCTION IF EXISTS public.payment_events_append_only()")
    op.execute("DROP TABLE IF EXISTS public.payments CASCADE")
